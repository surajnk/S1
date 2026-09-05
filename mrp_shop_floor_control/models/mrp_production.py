# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from datetime import datetime, time
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import pytz
import logging

_logger = logging.getLogger(__name__)

class MrpProduction(models.Model):
    _inherit = 'mrp.production'


    lot_producing_id = fields.Many2one(states={'done': [('readonly', True)]})
    user_id = fields.Many2one(states={'done': [('readonly', True)]})

    date_planned_start_pivot = fields.Datetime('Planned Start Pivot Date', default=fields.Datetime.now(), readonly=True, states={'draft': [('readonly', False)], 'confirmed': [('readonly', False)]})
    #date_planned_finished_pivot = fields.Datetime('Planned End Pivot Date', readonly=True, states={'draft': [('readonly', False)], 'confirmed': [('readonly', False)]}, compute='_compute_planned_pivot_finished_date', inverse='_set_planned_pivot_finished_date', store=True)
    date_planned_finished_pivot = fields.Datetime('Planned End Pivot Date', readonly=True, states={'draft': [('readonly', False)], 'confirmed': [('readonly', False)]}, compute='_compute_planned_pivot_finished_date', store=True)
    date_planned_start_wo = fields.Datetime(
        "Scheduled Start Date",
        readonly=True,
        states={'confirmed': [('readonly', False)],'progress': [('readonly', False)]},
    )
    date_planned_finished_wo = fields.Datetime("Scheduled End Date", readonly=True)
    date_actual_start_wo = fields.Datetime('Start Date', copy=False, readonly=True, compute="get_actual_dates", store=True)
    date_actual_finished_wo = fields.Datetime('End Date', copy=False, readonly=True, compute="get_actual_dates", store=True)
    origin = fields.Char(readonly=True, states={'draft': [('readonly', False)]})
    wo_confirmation = fields.Boolean('WO Confirmation Indicator', compute='_get_wo_confirmation', store=True)
    is_scheduled = fields.Boolean('Its Operations are Scheduled', compute='_compute_is_scheduled', store=True)
    put_up_rolls = fields.Float("Put Up(Rolls)")
    uom_put_up = fields.Float("Put up")
    put_up_uom_name = fields.Char()
    x_put_up_rolls = fields.Float("Put Up(Rolls)")
    x_uom_put_up = fields.Float("Put up")
    x_put_up_uom_name = fields.Char()
    outs = fields.Float("Outs")
    put_up_size = fields.Float("Put up size")
    addtnl_put_ups = fields.Float("Additional Put ups")
    skip_split = fields.Boolean("Skip Split(s)")
    x_dynamic_putup = fields.Boolean(string='Dynamic Put-ups', default=False)
    finished_move_line_ids = fields.One2many(
        'stock.move.line',
        compute='_compute_finished_move_line_ids',
        string='Finished Product Move Lines'
    )

    def _compute_finished_move_line_ids(self):
        for production in self:
            production.finished_move_line_ids = \
                production.move_finished_ids.filtered(
                    lambda m: not m.picking_id
                ).move_line_ids.filtered(
                    lambda ml: ml.qty_done > 0
                )

    @api.onchange('x_dynamic_putup')
    def _onchange_x_dynamic_putup(self):
        if self.x_dynamic_putup:
            self.outs = 1
            self.uom_put_up = 1
        else:
            self.outs = 0
            self.uom_put_up = 0

    # @api.onchange("put_up_rolls", "uom_put_up", "product_qty")
    # def onchange_for_quantity_validation(self):
    #     if self.put_up_rolls and self.uom_put_up:
    #         cal_qty = self.put_up_rolls * self.uom_put_up
    #         if cal_qty > self.product_qty:
    #             raise ValidationError(_("Can not exceed the Product Qty."))

    # @api.constrains("put_up_rolls", "uom_put_up", "product_qty")
    # def _validation_for_quantity(self):
    #     for line in self:
    #         if line.put_up_rolls and line.uom_put_up:
    #             cal_qty = line.put_up_rolls * line.uom_put_up
    #             if cal_qty > line.product_qty:
    #                 raise ValidationError(_("Can not exceed the Product Qty."))

    # @api.onchange("outs", "put_up_size", "x_customer_order_width")
    # def onchange_for_master_width_validation(self):
    #     """
    #     """
    #     if self.outs and self.put_up_size:
    #         cal_master_width = self.outs * self.put_up_size
    #         if cal_master_width > self.x_customer_order_width:
    #             raise ValidationError(_("Can not exceed the Master Width."))

    # @api.constrains("outs", "put_up_size", "x_customer_order_width")
    # def _check_master_width(self):
    #     for line in self:
    #         if line.outs and line.put_up_size:
    #             cal_master_width = line.outs * line.put_up_size
    #             if cal_master_width > line.x_customer_order_width:
    #                 raise ValidationError(_("Can not exceed the Master Width."))
    # def action_open_confirmed_date_suggestions(self):
    #     self.ensure_one()
    #     wiz = self.env["mrp.confirmed.date.suggestion.wizard"].create({
    #         "production_id": self.id,
    #     })
    #     return {
    #         "type": "ir.actions.act_window",
    #         "name": _("Suggested Confirmed Dates"),
    #         "res_model": "mrp.confirmed.date.suggestion.wizard",
    #         "view_mode": "form",
    #         "res_id": wiz.id,
    #         "target": "new",
    #     }

    def _generate_backorder_productions(self, close_mo=True):
        backorders = super()._generate_backorder_productions(close_mo)
        for backorder in backorders:
            backorder.qty_producing = 0
            backorder.state = 'confirmed'
        for workorder in backorders.workorder_ids:
            workorder.qty_produced = 0
            workorder.qty_producing = 0
        return backorders

    def action_capacity_check(self):
        return {
            'name': _('Capacity Check'),
            'view_mode': 'form',
            'res_model': 'mrp.capacity.check',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    @api.depends('x_mrp_confirmed_date', 'date_planned_start_pivot', 'product_id', 'company_id', 'picking_type_id')
    def _compute_planned_pivot_finished_date(self):
        date_start = False
        date_finished = False
        for production in self:
            if production.x_mrp_confirmed_date:
                date_start = datetime.combine(production.x_mrp_confirmed_date, datetime.min.time())
            else:
                date_start = production.date_planned_start_pivot or fields.Datetime.now()
            date_finished = date_start + relativedelta(days=production.product_id.produce_delay + 1)
            if production.company_id.manufacturing_lead > 0:
                date_finished = date_finished + relativedelta(days=production.company_id.manufacturing_lead + 1)
            if production.picking_type_id.warehouse_id.calendar_id:
                calendar = production.picking_type_id.warehouse_id.calendar_id
                date_start = calendar.plan_hours(0.0, date_start, True)
                date_finished = calendar.plan_days(production.product_id.produce_delay + 1, date_start, True)
                if production.company_id.manufacturing_lead > 0:
                    date_finished = calendar.plan_days(production.company_id.manufacturing_lead  + 1, date_finished, True)
            if date_finished == date_start:
                date_finished = date_start + relativedelta(hours=1)
            production.date_planned_start_pivot = date_start
            production.date_planned_finished_pivot = date_finished
        return True

    #def _set_planned_pivot_finished_date(self):
    #    date_start = False
    #    date_finished = False
    #    for production in self:
    #        if production.date_planned_finished_pivot:
    #            date_finished = production.date_planned_finished_pivot
    #            date_start = date_finished - relativedelta(days=production.product_id.produce_delay + 1)
    #            if production.company_id.manufacturing_lead > 0:
    #                date_start = date_start - relativedelta(days=production.company_id.manufacturing_lead + 1)
    #            if production.picking_type_id.warehouse_id.calendar_id:
    #                calendar = production.picking_type_id.warehouse_id.calendar_id
    #                date_finished = calendar.plan_hours(0.0, date_finished, True)
    #                date_start = calendar.plan_days(- production.product_id.produce_delay - 1, date_finished, True)
    #                if production.company_id.manufacturing_lead > 0:
    #                    date_start = calendar.plan_days(- production.company_id.manufacturing_lead - 1, date_start, True)
    #            if date_finished == date_start:
    #                date_start = date_finished + relativedelta(hours= -1)
    #        production.date_planned_start_pivot = date_start
    #        production.date_planned_finished_pivot = date_finished
    #    return True

    @api.depends("workorder_ids.date_planned_start_wo")
    def _compute_is_scheduled(self):
        for production in self:
            if production.workorder_ids:
                production.is_scheduled = any(workorder.date_planned_start_wo for workorder in production.workorder_ids if workorder.state not in ('done', 'cancel'))
            else:
                production.is_scheduled = False
        return True

    @api.depends('workorder_ids.state', 'is_scheduled')
    def _get_wo_confirmation(self):
        for production in self:
            production.wo_confirmation = False
            if any(workorder.state in ('pending','ready','progress') for workorder in production.workorder_ids) and production.is_scheduled:
                production.wo_confirmation = True
        return True

    def schedule_workorders(self):
        """
        Requirements implemented:
        - Start scheduling from NOW (never schedule the first WO in the past).
        - Use workcenter resource calendar working hours.
        - If a slot is occupied, find the next available slot (can move to later today or future days).
        - Respect workcenter capacity (parallelism).
        - The LAST workorder must finish on/before confirmed date at 05:00:00 America/New_York.
        - Keep existing interval_time gap between workorders.
        """
        # Server timezone is America/New_York (EDT/EST depending on DST).
        # confirmed_deadline is intended as "05:00 New_York time on confirmed date".
        # Odoo stores all datetimes in UTC internally. fields.Datetime.now() returns UTC.
        # We must convert the deadline to UTC before comparing or passing to slot finder.
        #
        # We use pytz.localize() instead of a hardcoded offset so DST is handled
        # automatically — EDT (UTC-4) in summer, EST (UTC-5) in winter.
        #
        # e.g. confirmed_date = 2026-03-25 (EDT active):
        #   05:00 New_York = 05:00 + 04:00 = 09:00 UTC same day
        NY_TZ = pytz.timezone('America/New_York')
        finite_boolean = self.env['ir.config_parameter'].sudo().get_param(
            'mrp_finite_capacity_control.finite_capacity_scheduling'
        )
        for production in self:
            # Capture user-set start date BEFORE clearing production dates.
            # button_plan guarantees this is set and not in the past.
            scheduling_cursor_start = production.date_planned_start_wo

            production.date_planned_start_wo = False
            production.date_planned_finished_wo = False

            # ---- Validations / inputs ----
            if not production.x_mrp_confirmed_date:
                raise UserError(_("Confirmed Date has not been entered"))

            # Build confirmed_deadline in UTC using proper pytz DST-aware conversion.
            confirmed_deadline_local = datetime.combine(
                production.x_mrp_confirmed_date, time(15, 0, 0)
            )
            confirmed_deadline = NY_TZ.localize(
                confirmed_deadline_local
            ).astimezone(pytz.utc).replace(tzinfo=None)

            _logger.info(
                "[Schedule] MO '%s' | Confirmed date: %s"
                " | Deadline local (NY): %s | Deadline UTC: %s",
                production.name,
                production.x_mrp_confirmed_date,
                confirmed_deadline_local,
                confirmed_deadline,
            )

            # Floating interval setup
            floating = self.env["mrp.floating.times"].search(
                [("warehouse_id", "=", production.picking_type_id.warehouse_id.id)],
                limit=1
            )
            if not floating:
                raise UserError(_(
                    "Floating Times record has not been created yet for the warehouse: %s"
                ) % production.picking_type_id.warehouse_id.name)

            yards = production.x_order_master_yards or 0
            if 0 < yards <= 10000:
                interval_minutes = floating.mrp_operations_first * 60
            elif yards <= 25000:
                interval_minutes = floating.mrp_operations_second * 60
            elif yards <= 50000:
                interval_minutes = floating.mrp_operations_third * 60
            elif yards <= 100000:
                interval_minutes = floating.mrp_operations_fourth * 60
            else:
                interval_minutes = floating.mrp_operations_fifth * 60

            _logger.info(
                "[Schedule] MO '%s' | Yards: %s | Interval between WOs: %s min",
                production.name, yards, interval_minutes,
            )

            # Workorders in routing sequence
            workorders = production.workorder_ids.sorted(key=lambda wo: (wo.sequence, wo.id))
            if not workorders:
                continue

            # Blocked operations check
            for wo in workorders:
                if wo.operation_id.occupied:
                    raise UserError(_("Operation has been blocked: %s") % wo.operation_id.name)

            # ---- Partial vs Full reschedule detection ----
            #
            # If ALL workorders already have dates → full reschedule (user
            # explicitly hit Schedule again, e.g. to force a fresh slot search).
            #
            # If SOME workorders have dates and SOME don't → partial reschedule:
            #   - WOs before the first unscheduled WO keep their existing slots
            #   - Cursor starts from the end of the last scheduled WO before
            #     the insertion point
            #   - All WOs from the insertion point onwards get cleared and
            #     rescheduled in sequence
            #
            # If NO workorders have dates → full reschedule from now.

            now = fields.Datetime.now()

            scheduled_wos = [wo for wo in workorders if wo.date_planned_start_wo]
            unscheduled_wos = [wo for wo in workorders if not wo.date_planned_start_wo]

            if unscheduled_wos and scheduled_wos:
                # ---- Partial reschedule ----
                # Find insertion point: first WO without dates
                first_unscheduled = unscheduled_wos[0]
                insertion_seq = first_unscheduled.sequence

                # WOs before insertion point keep their slots
                wos_before = [wo for wo in scheduled_wos if wo.sequence < insertion_seq]
                # WOs from insertion point onwards get rescheduled
                wos_to_reschedule = [wo for wo in workorders if wo.sequence >= insertion_seq]

                _logger.info(
                    "[Schedule] MO '%s' | PARTIAL RESCHEDULE | Insertion at seq %s"
                    " | Keeping %d WOs | Rescheduling %d WOs",
                    production.name, insertion_seq,
                    len(wos_before), len(wos_to_reschedule),
                )

                # Cursor = end of last WO before insertion point + interval
                if wos_before:
                    last_before = max(wos_before, key=lambda w: (w.sequence, w.id))
                    cursor = last_before.date_planned_start_wo + timedelta(
                        minutes=interval_minutes
                    )
                    _logger.info(
                        "[Schedule]   Cursor from last kept WO '%s' end: %s",
                        last_before.display_name, cursor,
                    )
                else:
                    cursor = scheduling_cursor_start
                    _logger.info(
                        "[Schedule]   No WOs before insertion point → cursor from date_planned_start_wo: %s",
                        cursor,
                    )

                # Clear dates on WOs being rescheduled
                for wo in wos_to_reschedule:
                    wo.write({
                        "date_planned_start_wo": False,
                        "date_planned_finished_wo": False,
                    })

            else:
                # ---- Full reschedule ----
                _logger.info(
                    "[Schedule] MO '%s' | FULL RESCHEDULE | WO count: %d",
                    production.name, len(workorders),
                )

                # Clear all dates
                production.date_planned_start_wo = False
                production.date_planned_finished_wo = False
                for wo in workorders:
                    wo.write({
                        "date_planned_start_wo": False,
                        "date_planned_finished_wo": False,
                    })

                wos_to_reschedule = list(workorders)
                # Use user-set date_planned_start_wo as cursor start.
                # button_plan already guarantees it is set and not in the past.
                cursor = scheduling_cursor_start

            _logger.info(
                "[Schedule] MO '%s' | Now (UTC): %s | Deadline (UTC): %s",
                production.name, now, confirmed_deadline,
            )

            if scheduling_cursor_start >= confirmed_deadline:
                raise UserError(_(
                    "Scheduled Start Date (%s) is at or after the confirmed deadline "
                    "(%s NY time). Please update the dates."
                ) % (
                    fields.Datetime.to_string(scheduling_cursor_start),
                    fields.Datetime.to_string(confirmed_deadline_local),
                ))

            # ---- Schedule the WOs ----
            for wo in wos_to_reschedule:
                wc = wo.workcenter_id
                if not wc:
                    raise UserError(_("Workorder %s has no workcenter.") % (wo.display_name,))

                _logger.info(
                    "[Schedule]   WO '%s' | WC '%s' | duration_expected: %.2f min"
                    " | cursor (UTC): %s | deadline (UTC): %s",
                    wo.display_name,
                    wc.display_name,
                    wo.duration_expected,
                    cursor,
                    confirmed_deadline,
                )

                slot_start, slot_end = wc._find_next_slot_in_working_hours(
                    start_dt=cursor,
                    duration_minutes=wo.duration_expected,
                    deadline_dt=confirmed_deadline,
                    same_day_only=False,
                    exclude_workorder=wo,
                )

                # AFTER (fixed)
                if not slot_start:
                    _logger.warning(
                        "[Schedule] No slot found for WO '%s' | WC '%s'"
                        " | cursor: %s | deadline: %s | duration: %.2f min",
                        wo.display_name, wc.display_name,
                        cursor, confirmed_deadline, wo.duration_expected,
                    )
                    if finite_boolean:
                        raise UserError(_(
                            "No available slot found for workorder %(wo)s on workcenter %(wc)s "
                            "before confirmed deadline %(dl)s (%(dl_ist)s NY time)."
                        ) % {
                            "wo": wo.display_name,
                            "wc": wc.display_name,
                            "dl": fields.Datetime.to_string(confirmed_deadline),
                            "dl_ist": fields.Datetime.to_string(confirmed_deadline_local),
                        })
                    # Non-finite: skip this WO, leave cursor unchanged
                    continue

                _logger.info(
                    "[Schedule]   WO '%s' → slot: %s – %s",
                    wo.display_name, slot_start, slot_end,
                )
                wo.write({
                    "date_planned_start_wo": slot_start,
                    "date_planned_finished_wo": slot_end,
                })
                cursor = slot_start + timedelta(minutes=interval_minutes)
                # if not slot_start  and finite_boolean:
                #     _logger.warning(
                #         "[Schedule] No slot found for WO '%s' | WC '%s'"
                #         " | cursor: %s | deadline: %s | duration: %.2f min",
                #         wo.display_name, wc.display_name,
                #         cursor, confirmed_deadline, wo.duration_expected,
                #     )
                #     raise UserError(_(
                #         "No available slot found for workorder %(wo)s on workcenter %(wc)s "
                #         "before confirmed deadline %(dl)s (%(dl_ist)s NY time)."
                #     ) % {
                #         "wo": wo.display_name,
                #         "wc": wc.display_name,
                #         "dl": fields.Datetime.to_string(confirmed_deadline),
                #         "dl_ist": fields.Datetime.to_string(confirmed_deadline_local),
                #     })

                # _logger.info(
                #     "[Schedule]   WO '%s' → slot: %s – %s",
                #     wo.display_name, slot_start, slot_end,
                # )

                # wo.write({
                #     "date_planned_start_wo": slot_start,
                #     "date_planned_finished_wo": slot_end,
                # })

                # cursor = slot_end + timedelta(minutes=interval_minutes)

            # ---- Save production planned dates from first/last WO ----
            all_scheduled = workorders.filtered(lambda w: w.date_planned_start_wo)
            if all_scheduled:
                production.date_planned_start_wo = all_scheduled[0].date_planned_start_wo
                production.date_planned_finished_wo = all_scheduled[-1].date_planned_finished_wo

            _logger.info(
                "[Schedule] MO '%s' | Scheduled: %s – %s | Deadline UTC: %s",
                production.name,
                production.date_planned_start_wo,
                production.date_planned_finished_wo,
                confirmed_deadline,
            )

            # Final hard safety check
            if (
                production.date_planned_finished_wo
                and production.date_planned_finished_wo > confirmed_deadline
            ):
                raise UserError(_(
                    "The last workorder finishes after the confirmed deadline (%s NY time)."
                ) % fields.Datetime.to_string(confirmed_deadline_local))

        return True

    # def schedule_workorders(self):
    #     """
    #     Requirements implemented:
    #     - Start scheduling from NOW (never schedule the first WO in the past).
    #     - Use workcenter resource calendar working hours.
    #     - If a slot is occupied, find the next available slot (can move to later today or future days).
    #     - Respect workcenter capacity (parallelism).
    #     - The LAST workorder must finish on/before confirmed date at 05:00:00 America/New_York.
    #     - Keep existing interval_time gap between workorders.
    #     """
    #     # Server timezone is America/New_York (EDT/EST depending on DST).
    #     # confirmed_deadline is intended as "05:00 New_York time on confirmed date".
    #     # Odoo stores all datetimes in UTC internally. fields.Datetime.now() returns UTC.
    #     # We must convert the deadline to UTC before comparing or passing to slot finder.
    #     #
    #     # We use pytz.localize() instead of a hardcoded offset so DST is handled
    #     # automatically — EDT (UTC-4) in summer, EST (UTC-5) in winter.
    #     #
    #     # e.g. confirmed_date = 2026-03-25 (EDT active):
    #     #   05:00 New_York = 05:00 + 04:00 = 09:00 UTC same day
    #     NY_TZ = pytz.timezone('America/New_York')

    #     for production in self:
    #         production.date_planned_start_wo = False
    #         production.date_planned_finished_wo = False

    #         # ---- Validations / inputs ----
    #         if not production.x_mrp_confirmed_date:
    #             raise UserError(_("Confirmed Date has not been entered"))

    #         # Build confirmed_deadline in UTC using proper pytz DST-aware conversion.
    #         confirmed_deadline_local = datetime.combine(
    #             production.x_mrp_confirmed_date, time(5, 0, 0)
    #         )
    #         confirmed_deadline = NY_TZ.localize(
    #             confirmed_deadline_local
    #         ).astimezone(pytz.utc).replace(tzinfo=None)

    #         _logger.info(
    #             "[Schedule] MO '%s' | Confirmed date: %s"
    #             " | Deadline local (NY): %s | Deadline UTC: %s",
    #             production.name,
    #             production.x_mrp_confirmed_date,
    #             confirmed_deadline_local,
    #             confirmed_deadline,
    #         )

    #         # Floating interval setup
    #         floating = self.env["mrp.floating.times"].search(
    #             [("warehouse_id", "=", production.picking_type_id.warehouse_id.id)],
    #             limit=1
    #         )
    #         if not floating:
    #             raise UserError(_(
    #                 "Floating Times record has not been created yet for the warehouse: %s"
    #             ) % production.picking_type_id.warehouse_id.name)

    #         yards = production.x_order_master_yards or 0
    #         if 0 < yards <= 10000:
    #             interval_minutes = floating.mrp_operations_first * 60
    #         elif yards <= 25000:
    #             interval_minutes = floating.mrp_operations_second * 60
    #         elif yards <= 50000:
    #             interval_minutes = floating.mrp_operations_third * 60
    #         elif yards <= 100000:
    #             interval_minutes = floating.mrp_operations_fourth * 60
    #         else:
    #             interval_minutes = floating.mrp_operations_fifth * 60

    #         _logger.info(
    #             "[Schedule] MO '%s' | Yards: %s | Interval between WOs: %s min",
    #             production.name, yards, interval_minutes,
    #         )

    #         # Workorders in routing sequence
    #         workorders = production.workorder_ids.sorted(key=lambda wo: (wo.sequence, wo.id))
    #         if not workorders:
    #             continue

    #         # Blocked operations check
    #         for wo in workorders:
    #             if wo.operation_id.occupied:
    #                 raise UserError(_("Operation has been blocked: %s") % wo.operation_id.name)

    #         # ---- Scheduling ----
    #         now = fields.Datetime.now()

    #         _logger.info(
    #             "[Schedule] MO '%s' | Now (UTC): %s | Deadline (UTC): %s"
    #             " | WO count: %d",
    #             production.name, now, confirmed_deadline, len(workorders),
    #         )

    #         if now >= confirmed_deadline:
    #             raise UserError(_(
    #                 "Confirmed deadline (%s NY time) is already in the past."
    #                 " Please update Confirmed Date."
    #             ) % fields.Datetime.to_string(confirmed_deadline_local))

    #         cursor = now  # start from now; never schedule in the past

    #         for wo in workorders:
    #             wc = wo.workcenter_id
    #             if not wc:
    #                 raise UserError(_("Workorder %s has no workcenter.") % (wo.display_name,))

    #             _logger.info(
    #                 "[Schedule]   WO '%s' | WC '%s' | duration_expected: %.2f min"
    #                 " | cursor (UTC): %s | deadline (UTC): %s",
    #                 wo.display_name,
    #                 wc.display_name,
    #                 wo.duration_expected,
    #                 cursor,
    #                 confirmed_deadline,
    #             )

    #             slot_start, slot_end = wc._find_next_slot_in_working_hours(
    #                 start_dt=cursor,
    #                 duration_minutes=wo.duration_expected,
    #                 deadline_dt=confirmed_deadline,
    #                 same_day_only=False,
    #                 exclude_workorder=wo,
    #             )

    #             if not slot_start:
    #                 _logger.warning(
    #                     "[Schedule] No slot found for WO '%s' | WC '%s'"
    #                     " | cursor: %s | deadline: %s | duration: %.2f min",
    #                     wo.display_name, wc.display_name,
    #                     cursor, confirmed_deadline, wo.duration_expected,
    #                 )
    #                 raise UserError(_(
    #                     "No available slot found for workorder %(wo)s on workcenter %(wc)s "
    #                     "before confirmed deadline %(dl)s (%(dl_ist)s NY time)."
    #                 ) % {
    #                     "wo": wo.display_name,
    #                     "wc": wc.display_name,
    #                     "dl": fields.Datetime.to_string(confirmed_deadline),
    #                     "dl_ist": fields.Datetime.to_string(confirmed_deadline_local),
    #                 })

    #             _logger.info(
    #                 "[Schedule]   WO '%s' → slot: %s – %s",
    #                 wo.display_name, slot_start, slot_end,
    #             )

    #             wo.write({
    #                 "date_planned_start_wo": slot_start,
    #                 "date_planned_finished_wo": slot_end,
    #             })

    #             # Move cursor forward: end of this WO + interval gap
    #             cursor = slot_end + timedelta(minutes=interval_minutes)

    #         # ---- Save production planned dates from first/last WO ----
    #         production.date_planned_start_wo = workorders[0].date_planned_start_wo
    #         production.date_planned_finished_wo = workorders[-1].date_planned_finished_wo

    #         _logger.info(
    #             "[Schedule] MO '%s' | Scheduled: %s – %s | Deadline UTC: %s",
    #             production.name,
    #             production.date_planned_start_wo,
    #             production.date_planned_finished_wo,
    #             confirmed_deadline,
    #         )

    #         # Final hard safety check
    #         if (
    #             production.date_planned_finished_wo
    #             and production.date_planned_finished_wo > confirmed_deadline
    #         ):
    #             raise UserError(_(
    #                 "The last workorder finishes after the confirmed deadline (%s NY time)."
    #             ) % fields.Datetime.to_string(confirmed_deadline_local))

    #     return True
    # scheduling custom
    # def schedule_workorders(self):
    #     max_date_finished = False
    #     start_date = False
    #     interval_time = 0.0
    #     for production in self:
    #         production.date_planned_start_wo = False
    #         production.date_planned_finished_wo = False
    #         floating_times_id = self.env['mrp.floating.times'].search([('warehouse_id', '=', production.picking_type_id.warehouse_id.id)])
    #         floating_times_id_new = self.env['mrp.floating.times'].search([('warehouse_id', '=', production.picking_type_id.warehouse_id.id)])
    #         if (production.x_order_master_yards > 0 and production.x_order_master_yards <= 10000):
    #             interval_time = (floating_times_id_new.mrp_operations_first * 60)
    #         if (production.x_order_master_yards > 10000 and production.x_order_master_yards <= 25000):
    #             interval_time = (floating_times_id_new.mrp_operations_second * 60)
    #         if (production.x_order_master_yards > 25000 and production.x_order_master_yards <= 50000):
    #             interval_time = (floating_times_id_new.mrp_operations_third * 60)
    #         if (production.x_order_master_yards > 50000 and production.x_order_master_yards <= 100000):
    #             interval_time = (floating_times_id_new.mrp_operations_fourth * 60)
    #         if (production.x_order_master_yards > 100000):
    #             interval_time = (floating_times_id_new.mrp_operations_fifth * 60)
    #         if not floating_times_id:
    #             raise UserError(_('Floating Times record has not been created yet for the warehouse: %s')% production.picking_type_id.warehouse_id.name)
    #         warehouse_calendar = production.picking_type_id.warehouse_id.calendar_id
            
    #         if not production.x_mrp_confirmed_date:
    #             raise UserError(_('Confirmed Date has not been entered'))
    #         if production.x_mrp_confirmed_date:
    #             start_date = datetime.combine(production.x_mrp_confirmed_date, datetime.min.time())
    #         else:
    #             start_date = fields.Datetime.now()
    #         # Release production
    #         for workorder in production.workorder_ids:
    #             if workorder.operation_id.occupied:
    #                 raise UserError(_('Operation has been blocked:%s')% workorder.operation_id.name)
    #         # workorders scheduling
    #         workorders = production.workorder_ids.sorted(key=lambda wo: (wo.sequence, wo.id))
    #         duration_expected = sum(workorders.mapped('duration_expected'))
    #         workorder_count = len(workorders)
            
    #         # Compute the total interval time to subtract
    #         total_interval_time = timedelta(minutes=duration_expected + (interval_time * (workorder_count - 1)))
            
    #         start_date -= total_interval_time
    #         if start_date < fields.Datetime.now():
    #             first_workorder = workorders[0] if workorders else False
    #             operation_name = first_workorder.operation_id.name if first_workorder else _('Unknown operation')
    #             workcenter_name = first_workorder.workcenter_id.name if first_workorder else _('Unknown workcenter')
    #             raise UserError(_(
    #                 'Work orders cannot be scheduled in the past. '
    #                 'Operation: %s, Workcenter: %s. '
    #                 'Please update the confirmed date.'
    #             ) % (operation_name, workcenter_name))
    #         production.date_planned_start_wo = start_date
    #         for workorder in production.workorder_ids:

    #             if not workorder.prev_work_order_id:
    #                 workorder.date_planned_start_wo = start_date
    #                 calendar = workorder.workcenter_id.resource_calendar_id
    #                 if calendar:
    #                     workorder.date_planned_start_wo = calendar.plan_hours(0.0, workorder.date_planned_start_wo, True)
    #             else:
    #                 if workorder.prev_work_order_id:
    #                     workorder.date_planned_start_wo = calendar.plan_hours(interval_time, workorder.date_planned_start_wo, True)

    #             end_date = start_date + timedelta(minutes=workorder.duration_expected)
    #             workorder.write({'date_planned_start_wo': start_date,'date_planned_finished_wo': end_date})
    #             start_date = end_date + timedelta(minutes=interval_time)
    
    #         # after production
    #         production.date_planned_finished_wo = production.x_mrp_confirmed_date.strftime('%Y-%m-%d 00:00:00')
    #     return True


    # def schedule_workorders(self):
    #     max_date_finished = False
    #     start_date = False
    #     for production in self:
    #         production.date_planned_start_wo = False
    #         production.date_planned_finished_wo = False
    #         floating_times_id = self.env['mrp.floating.times'].search([('warehouse_id', '=', production.picking_type_id.warehouse_id.id)])
    #         if not floating_times_id:
    #             raise UserError(_('Floating Times record has not been created yet for the warehouse: %s')% production.picking_type_id.warehouse_id.name)
    #         warehouse_calendar = production.picking_type_id.warehouse_id.calendar_id
    #         start_date = production.date_planned_start_pivot or fields.Datetime.now()
    #         # Release production
    #         release_time = floating_times_id.mrp_release_time
    #         if release_time > 0.0 and warehouse_calendar:
    #             start_date = warehouse_calendar.plan_hours(release_time, start_date, True)
    #         production.date_planned_start_wo = start_date
    #         # before production
    #         before_production_time = floating_times_id.mrp_ftbp_time
    #         if before_production_time > 0.0 and warehouse_calendar:
    #             start_date = warehouse_calendar.plan_hours(before_production_time, start_date, True)
    #         for workorder in production.workorder_ids:
    #             if workorder.operation_id.occupied:
    #                 raise UserError(_('Operation has been blocked:%s')% workorder.operation_id.name)
    #         # workorders scheduling
    #         for workorder in production.workorder_ids:
    #             if not workorder.prev_work_order_id:
    #                 workorder.date_planned_start_wo = start_date
    #                 calendar = workorder.workcenter_id.resource_calendar_id
    #                 if calendar:
    #                     workorder.date_planned_start_wo = calendar.plan_hours(0.0, workorder.date_planned_start_wo, True)
    #             else:
    #                 if not workorder.sequence == workorder.prev_work_order_id.sequence:
    #                     workorder.date_planned_start_wo = max_date_finished or workorder.prev_work_order_id.date_planned_finished_wo
    #                 else:
    #                     workorder.date_planned_start_wo = workorder.prev_work_order_id.date_planned_start_wo
    #             workorder.forwards_scheduling()
    #             if workorder.prev_work_order_id:
    #                 max_date_finished = max(workorder.date_planned_finished_wo, workorder.prev_work_order_id.date_planned_finished_wo)
    #             else:
    #                 max_date_finished = workorder.date_planned_finished_wo
    #         # after production
    #         after_production_time = floating_times_id.mrp_ftap_time
    #         if after_production_time > 0.0 and warehouse_calendar:
    #             max_date_finished = warehouse_calendar.plan_hours(after_production_time, max_date_finished, True)
    #         production.date_planned_finished_wo = max_date_finished
    #     return True

    def button_plan(self):
        # --- Validate date_planned_start_wo before scheduling ---
        for production in self:
            if not production.date_planned_start_wo:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Warning'),
                        'message': _(
                            'Scheduled Start Date is not set on Manufacturing Order %s. '
                            'Please set it before scheduling workorders.'
                        ) % production.name,
                        'sticky': False,
                        'type': 'warning',
                    },
                }
            if production.date_planned_start_wo < fields.Datetime.now():
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Warning'),
                        'message': _(
                            'Scheduled Start Date on Manufacturing Order %s is in the past. '
                            'Please set a future date before scheduling workorders.'
                        ) % production.name,
                        'sticky': False,
                        'type': 'warning',
                    },
                }
        res = super().button_plan()
        workorder_count = 0
        n = 0
        for production in self:
            production.schedule_workorders()
            # _logger.info("QUANTITYYYY '%s'",production.x_order_master_yards)
            # so_rec = self.env['sale.order'].search([('name', '=', production.origin)])
            # floating_times_id_new = self.env['mrp.floating.times'].search([('warehouse_id', '=', production.picking_type_id.warehouse_id.id)])
            # if (production.x_order_master_yards > 0 and production.x_order_master_yards <= 10000):
            #     interval_time = (floating_times_id_new.mrp_operations_first * 60)
            # if (production.x_order_master_yards > 10000 and production.x_order_master_yards <= 25000):
            #     interval_time = (floating_times_id_new.mrp_operations_second * 60)
            # if (production.x_order_master_yards > 25000 and production.x_order_master_yards <= 50000):
            #     interval_time = (floating_times_id_new.mrp_operations_third * 60)
            # if (production.x_order_master_yards > 50000 and production.x_order_master_yards <= 100000):
            #     interval_time = (floating_times_id_new.mrp_operations_fourth * 60)
            # if (production.x_order_master_yards > 100000):
            #     interval_time = (floating_times_id_new.mrp_operations_fifth * 60)
            # if production.x_mrp_confirmed_date:
            #     production.date_planned_finished_wo = production.x_mrp_confirmed_date.strftime('%Y-%m-%d 00:00:00')
            #     duration_expected = sum(production.workorder_ids.mapped('duration_expected'))
            #     workorder_count = len(production.workorder_ids)
            #     production.date_planned_start_wo = production.date_planned_finished_wo - timedelta(
            #         minutes=duration_expected+(interval_time*(workorder_count-1)))
            #     start_date = production.date_planned_start_wo
            #     for workorder in production.workorder_ids:
            #         end_date = start_date + timedelta(minutes=workorder.duration_expected)
            #         workorder.write({'date_planned_start_wo': start_date,'date_planned_finished_wo': end_date})
            #         # workorder.mid_point_scheduling_engine()
            #         start_date = start_date + timedelta(minutes=workorder.duration_expected+interval_time)
            #         end_date = ' '
            # else:
            #     if so_rec and so_rec.commitment_date:
            #         production.date_planned_finished_wo = so_rec.commitment_date
            #         duration_expected = sum(production.workorder_ids.mapped('duration_expected'))
            #         workorder_count = len(production.workorder_ids)
            #         production.date_planned_start_wo = production.date_planned_finished_wo - timedelta(
            #         minutes=duration_expected+(interval_time*(workorder_count-1)))
            #         start_date = production.date_planned_start_wo
            #         for workorder in production.workorder_ids:
            #             end_date = start_date + timedelta(minutes=workorder.duration_expected)
            #             workorder.write({'date_planned_start_wo': start_date,'date_planned_finished_wo': end_date})
            #             #workorder.mid_point_scheduling_engine()
            #             start_date = start_date + timedelta(minutes=workorder.duration_expected+interval_time)
            #             end_date = ' '
                # for workorder in production.workorder_ids:
                #     workorder.date_planned_start_wo = start_date
                #     start_date = start_date + timedelta(minutes=workorder.duration_expected+interval_time)
        return res

    ## delete workload
    def button_unplan(self):
        res = super().button_unplan()
        for production in self:
            for workorder in production.workorder_ids:
                workorder.date_planned_start_wo = False
                workorder.date_planned_finished_wo = False
            wo_capacity_ids = self.env['mrp.workcenter.capacity'].search([('workorder_id', 'in', production.workorder_ids.ids)])
            wo_capacity_ids.unlink()
            production.date_planned_start_wo = False
            production.date_planned_finished_wo = False
        return res

    @api.depends('state')
    def get_actual_dates(self):
        for production in self:
            if production.workorder_ids:
                if production.state == "done" and production.workorder_ids:
                    workorders = self.env['mrp.workorder'].search([('production_id', '=', production.id),('state', '=', 'done')])
                    time_records = self.env['mrp.workcenter.productivity'].search([('workorder_id', 'in', workorders.ids)])
                    if time_records:
                        production.date_actual_start_wo = time_records.sorted('date_start')[0].date_start
                        production.date_actual_finished_wo = time_records.sorted('date_end')[-1].date_end
            else:
                if production.state == "confirmed":
                    production.write({'date_actual_start_wo': fields.Datetime.now()})
                if production.state == "done":
                    production.write({'date_actual_finished_wo': fields.Datetime.now()})
        return True

    ## delete workload
    def action_cancel(self):
        for production in self:
            if production.workorder_ids:
                wo_capacity_ids = self.env['mrp.workcenter.capacity'].search([('workorder_id', 'in', production.workorder_ids.ids)])
                wo_capacity_ids.unlink()
                if any(workorder.state == 'progress' for workorder in production.workorder_ids):
                    raise UserError(_('workorder still running, please close it'))
        return super().action_cancel()

    def button_mark_done(self):
        for production in self:
            if production.workorder_ids:
                if any(workorder.state not in ('done', 'cancel') for workorder in production.workorder_ids):
                    raise UserError(_('workorders not yet processed, please close them before'))
            # if any(picking_id.state not in ('done', 'cancel') for picking_id in production.picking_ids):
            #     raise UserError(_('pickings not yet processed, please close or cancel them'))
            # if self.put_up_rolls > 0:
            #     self.generate_finish_move_line()
        return super().button_mark_done()

    # def generate_finish_move_line(self):
    #     """
    #     """
    #     print ("\n\n\n BBBBBBBBBBBBBBBB Generate Finish Line ----------------")
    #     # remove Exist Lines
    #     if self.put_up_rolls:
    #         print ("self.move_finished_ids",self.move_finished_ids)
    #         for finish_mv_line in self.move_finished_ids:
    #         #     for rm_mv_line in finish_mv_line.move_line_ids:
    #         #         finish_mv_line.move_line_ids = [(2, rm_mv_line.id)]
    #             print ("\n\n\n BBBBBBBBBBBBBBBBBBBBBBB",finish_mv_line)
    #     20 / 0
                # for finish_mv in finish_mv_line:
                #     for l in range(0, int(self.put_up_rolls)):
                #         qty = self.product_qty/self.put_up_rolls
                #         move_line_vals = finish_mv._prepare_move_line_vals(quantity=qty)
                #         if finish_mv.product_id and finish_mv.product_id.tracking == 'lot':
                #             new_lot = self.env['stock.production.lot'].create({
                #                 'product_id': finish_mv.product_id.id,
                #                 'company_id': self.company_id.id})
                #             new_lot.name = self.name + '/' + new_lot.name
                #             move_line_vals['lot_id'] = new_lot.id
                #         move_line_vals['product_uom_id'] = finish_mv.product_id.uom_id.id
                #         move_line_vals['qty_done'] = qty
                #         finish_mv_line.move_line_ids = [(0, 0, move_line_vals)]

    # def generate_finish_move_line(self):
    #     """
    #     """
    #     # remove Exist Lines
    #     if self.put_up_rolls:
    #         for finish_mv_line in self.move_finished_ids:
    #             for rm_mv_line in finish_mv_line.move_line_ids:
    #                 finish_mv_line.move_line_ids = [(2, rm_mv_line.id)]
    #
    #             for finish_mv in finish_mv_line:
    #                 for l in range(0, int(self.put_up_rolls)):
    #                     qty = self.product_qty/self.put_up_rolls
    #                     move_line_vals = finish_mv._prepare_move_line_vals(quantity=qty)
    #                     if finish_mv.product_id and finish_mv.product_id.tracking == 'lot':
    #                         new_lot = self.env['stock.production.lot'].create({
    #                             'product_id': finish_mv.product_id.id,
    #                             'company_id': self.company_id.id})
    #                         new_lot.name = self.name + '/' + new_lot.name
    #                         move_line_vals['lot_id'] = new_lot.id
    #                     move_line_vals['product_uom_id'] = finish_mv.product_id.uom_id.id
    #                     move_line_vals['qty_done'] = qty
    #                     finish_mv_line.move_line_ids = [(0, 0, move_line_vals)]