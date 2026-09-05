# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpWoSchedulingWizard(models.TransientModel):
    _name = "mrp.wo.scheduling.wizard"
    _description = 'MRP WO Scheduling Wizard'

    @api.model
    def default_get(self, fields):
        res = super(MrpWoSchedulingWizard, self).default_get(fields)
        mrp_workorder_ids = self._context.get('mrp_workorder_ids')
        WorkOrders = self.env['mrp.workorder'].sudo().browse(mrp_workorder_ids)
        vals = [{
            'workorder_id': WorkOrder.id,
            'sequence': WorkOrder.schedule_sequence,
            'workcenter_id': WorkOrder.workcenter_id.id,
            'production_id': WorkOrder.production_id.id,
            'date_planned_start_wo': WorkOrder.date_planned_start_wo,
            'duration_expected': WorkOrder.duration_expected,
            'duration_expected_hrs': WorkOrder.duration_expected_hrs,
            'operation_id': WorkOrder.operation_id.id,
            'x_order_customer_mrp_wo_width': WorkOrder.x_order_customer_mrp_wo_width,
            'x_order_customer_mrp_wo_length': WorkOrder.x_order_customer_mrp_wo_length,
            'x_order_customer_mrp_wo_qty': WorkOrder.x_order_customer_mrp_wo_qty,
            'qty_output_wo': WorkOrder.qty_output_wo,
            'width': WorkOrder.width,
            'trim': WorkOrder.trim,
            'base_avail': WorkOrder.base_avail,
            't_c': WorkOrder.t_c,
            'rod': WorkOrder.rod,
        } for WorkOrder in WorkOrders]
        res['wo_schedule_ids'] = [(0, 0, r) for r in vals]
        return res

    wo_schedule_ids = fields.One2many('mrp.wo.scheduling', 'wizard_id', string='Work Center')
    set_scheduled_datetime = fields.Datetime(string='Scheduled Start Date', required=1)

    def _compute_slots(self):
        """
        Core slot-finding logic shared by calc_scheduled_date (preview)
        and do_confirm (write).

        For each WO line sorted by sequence:
          - Uses workcenter._find_next_slot_in_working_hours() starting from
            set_scheduled_datetime, respecting working hours, finite capacity,
            and dynamic per-shift x_capacity.
          - Passes exclude_workorder=wo so the WO's own existing slot is not
            counted against capacity.
          - Each WO searches independently from set_scheduled_datetime —
            capacity parallelism handles overlap naturally (e.g. if capacity=4,
            first 4 WOs may get overlapping slots).

        Returns a list of dicts:
          [{'line': <mrp.wo.scheduling>, 'slot_start': dt, 'slot_end': dt}, ...]

        Raises UserError if no slot found for any WO.
        """
        start_dt = self.set_scheduled_datetime
        if not start_dt:
            raise UserError(_("Please set a Scheduled Start Date first."))

        results = []
        for line in self.wo_schedule_ids.sorted(lambda g: g.sequence):
            wc = line.workcenter_id
            wo = line.workorder_id

            if not wc:
                raise UserError(_(
                    "Work Order %s has no workcenter assigned."
                ) % wo.display_name)

            if not line.duration_expected or line.duration_expected <= 0:
                raise UserError(_(
                    "Work Order %s has no expected duration."
                ) % wo.display_name)

            slot_start, slot_end = wc._find_next_slot_in_working_hours(
                start_dt=start_dt,
                duration_minutes=line.duration_expected,
                deadline_dt=None,
                same_day_only=False,
                exclude_workorder=wo,
            )

            if not slot_start:
                raise UserError(_(
                    "No available slot found for Work Order %(wo)s "
                    "on Workcenter %(wc)s starting from %(dt)s."
                ) % {
                    'wo': wo.display_name,
                    'wc': wc.display_name,
                    'dt': fields.Datetime.to_string(start_dt),
                })

            results.append({
                'line': line,
                'slot_start': slot_start,
                'slot_end': slot_end,
            })

        return results

    def calc_scheduled_date(self):
        """
        Preview: compute slots and update wizard line dates only.
        Does NOT write to actual workorders yet.
        Re-opens the wizard so user can review before confirming.
        """
        slots = self._compute_slots()

        for slot in slots:
            # Write to transient wizard line only (readonly=False needed — see note)
            slot['line'].write({
                'date_planned_start_wo': slot['slot_start'],
                'date_planned_finished_wo': slot['slot_end'],
            })

        return {
            'context': self.env.context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mrp.wo.scheduling.wizard',
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def do_confirm(self):
        """
        Confirm: re-compute slots (fresh, authoritative) and write to actual
        workorders. Then build a warning listing affected MOs so the user
        knows to re-run schedule_workorders on them if needed.
        """
        slots = self._compute_slots()

        # --- Write slots to actual workorders ---
        affected_productions = set()
        for slot in slots:
            wo = slot['line'].workorder_id
            wo.write({
                'date_planned_start_wo': slot['slot_start'],
                'date_planned_finished_wo': slot['slot_end'],
                'schedule_sequence': slot['line'].sequence,
            })
            affected_productions.add(wo.production_id)

        # --- Update production planned dates from their WOs ---
        for production in affected_productions:
            scheduled_wos = production.workorder_ids.filtered(
                lambda w: w.date_planned_start_wo and w.date_planned_finished_wo
            )
            if scheduled_wos:
                production.date_planned_start_wo = min(
                    scheduled_wos.mapped('date_planned_start_wo')
                )
                production.date_planned_finished_wo = max(
                    scheduled_wos.mapped('date_planned_finished_wo')
                )

        # --- Build warning message for affected MOs ---
        # These MOs have other WOs (predecessors/successors) whose dates
        # may now be misaligned. User should re-run schedule_workorders on them.
        affected_mo_names = sorted([p.name for p in affected_productions])
        warning_msg = _(
            "Slots have been assigned successfully.\n\n"
            "The following Manufacturing Orders have been affected and may "
            "need to be rescheduled to realign their other workorders:\n\n%s"
        ) % '\n'.join('• %s' % name for name in affected_mo_names)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Scheduling Complete'),
                'message': warning_msg,
                'type': 'warning',
                'sticky': True,
            },
        }


class MrpWoScheduling(models.TransientModel):
    _name = "mrp.wo.scheduling"
    _description = 'MRP WO Scheduling'

    wizard_id = fields.Many2one('mrp.wo.scheduling.wizard', string='WO Scheduling')
    workorder_id = fields.Many2one('mrp.workorder', string='Work Order', readonly=1)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center', readonly=1)
    production_id = fields.Many2one('mrp.production', string='Production Order', readonly=1)
    sequence = fields.Integer(string='Sequence', default=1, required=1)

    # Stored on the transient line so calc_scheduled_date can preview
    # both start and end without touching actual WO records yet.
    date_planned_start_wo = fields.Datetime(string='Scheduled Start Date')
    date_planned_finished_wo = fields.Datetime(string='Scheduled End Date')

    duration_expected = fields.Float(
        string='Expected Duration', related='workorder_id.duration_expected', readonly=1)
    duration_expected_hrs = fields.Float(
        string='Expected Duration(Hrs)', related='workorder_id.duration_expected_hrs', readonly=1)
    operation_id = fields.Many2one(
        'mrp.routing.workcenter', string='Operation', related='workorder_id.operation_id')
    x_order_customer_mrp_wo_width = fields.Char(
        string='Cust Wid', related='workorder_id.x_order_customer_mrp_wo_width')
    x_order_customer_mrp_wo_length = fields.Char(
        string='Cust Len', related='workorder_id.x_order_customer_mrp_wo_length')
    x_order_customer_mrp_wo_qty = fields.Char(
        string='Cust Qty', related='workorder_id.x_order_customer_mrp_wo_qty')
    width = fields.Char(string='Width', related='workorder_id.width')
    trim = fields.Char(string='Trim', related='workorder_id.trim')
    base_avail = fields.Char(string='Base', related='workorder_id.base_avail')
    t_c = fields.Char(string='T/C', related='workorder_id.t_c')
    rod = fields.Integer(string='ROD', related='workorder_id.rod')
    shaded = fields.Boolean(string='Shaded', related='workorder_id.shaded')
    qty_output_wo = fields.Float(string='WO Qty', related='workorder_id.qty_output_wo')