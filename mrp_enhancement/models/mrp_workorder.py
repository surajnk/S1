# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'


    roll_line_ids = fields.One2many(inverse="_inverse_roll_line_ids")
    setup_time = fields.Float(string='Setup time', readoly=1)
    # cleanup_time = fields.Float(string='Cleanup time', readonly=1)

    put_up_rolls = fields.Float(related="production_id.put_up_rolls", string="Put Up(Rolls)")
    uom_put_up = fields.Float(related="production_id.uom_put_up", string="Put up")
    put_up_uom_name = fields.Char(related='product_uom_id.name')
    outs = fields.Float(related="production_id.outs", string="Outs")
    put_up_size = fields.Float(related="production_id.put_up_size", string="Put up size")
    final_roll_line_ids = fields.One2many('final.wo.roll', 'workorder_id', string='Final Roll Lines')
    total_final_yards_qty = fields.Float(
        string='Total Final Yards',
        compute='_compute_total_final_yards_qty',
        store=True,
        readonly=True,
    )


    def _action_confirm(self):
        # Odoo14 core sometimes calls _action_confirm() on an empty recordset
        # during unlink() flush of workorder_ids, which crashes on workorders[0].
        if not self:
            _logger.info("mrp.workorder._action_confirm called on empty recordset -> skip")
            return False
        return super()._action_confirm()

    def _inverse_roll_line_ids(self):
        for workorder in self:
            #workorder.qty_produced = sum(workorder.roll_line_ids.mapped('quantity'))
            workorder.total_produce_quantity = sum(workorder.roll_line_ids.mapped('quantity'))

    @api.depends('final_roll_line_ids', 'final_roll_line_ids.yards_qty')
    def _compute_total_final_yards_qty(self):
        for workorder in self:
            workorder.total_final_yards_qty = sum(workorder.final_roll_line_ids.mapped('yards_qty'))

    def action_open_roll_transfer_wizard(self):
        wo_ids = self.env.context.get('active_ids', self.ids)
        workorders = self.env['mrp.workorder'].browse(wo_ids)

        lines = []
        for wo in workorders:
            prev_wo = wo.production_id.workorder_ids.filtered(
                lambda w: w.sequence < wo.sequence
            ).sorted('sequence', reverse=True)[:1]

            if not prev_wo or not prev_wo.workcenter_id or not prev_wo.workcenter_id.location_id:
                continue

            pickings = self.env['stock.picking'].search([
                ('origin', '=', wo.production_id.name),
                ('location_id', '=', prev_wo.workcenter_id.location_id.id),
                ('picking_type_code', '=', 'internal'),
                ('state', 'not in', ['cancel']),
                ('is_reverse_transfer', '=', False),
            ])
            for picking in pickings:
                lines.append((0, 0, {
                    'picking_id': picking.id,
                    'workorder_id': prev_wo.id,
                    'target_workorder_id': wo.id,
                    'state': picking.state,
                    'selected': False,
                }))

        wizard = self.env['roll.transfer.wizard'].create({
            'transfer_line_ids': lines,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Roll Transfers',
            'res_model': 'roll.transfer.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }

    # def action_open_roll_transfer_wizard(self):
    #     wo_ids = self.env.context.get('active_ids', self.ids)
    #     workorders = self.env['mrp.workorder'].browse(wo_ids)

    #     lines = []
    #     for wo in workorders:
    #         if not wo.workcenter_id or not wo.workcenter_id.location_id:
    #             continue
    #         pickings = self.env['stock.picking'].search([
    #             ('origin', '=', wo.production_id.name),
    #             ('location_id', '=', wo.workcenter_id.location_id.id),
    #             ('picking_type_code', '=', 'internal'),
    #             ('state', 'not in', ['cancel']),
    #             ('is_reverse_transfer', '=', False),
    #         ])
    #         for picking in pickings:
    #             lines.append((0, 0, {
    #                 'picking_id': picking.id,
    #                 'workorder_id': wo.id,
    #                 'state': picking.state,
    #                 'selected': False,
    #             }))

    #     wizard = self.env['roll.transfer.wizard'].create({
    #         'transfer_line_ids': lines,
    #     })

    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Roll Transfers',
    #         'res_model': 'roll.transfer.wizard',
    #         'res_id': wizard.id,
    #         'view_mode': 'form',
    #         'target': 'new',
    #     }

    def button_start_wiz(self):
        self.ensure_one()

        # Guard: if timer_id is set but the extra.time record no longer exists
        # (e.g. from a duplicated MO), clear it and open fresh wizard.
        if self.timer_id:
            timer_exists = self.env['extra.time'].browse(
                self.timer_id).exists()
            if not timer_exists:
                self.timer_id = 0  # clear stale reference

        if not self.timer_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _("Enter time"),
                'view_mode': 'form',
                'res_model': 'extra.time',
                'views': [(False, 'form')],
                'target': 'new',
                'context': {
                    'active_id': self.id,
                    'from_start': True,
                    'workcenter_id': self.workcenter_id and self.workcenter_id.id or False,
                }
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _("Enter time"),
                'view_mode': 'form',
                'res_model': 'extra.time',
                'views': [(False, 'form')],
                'target': 'new',
                'res_id': self.timer_id,  # already an int — correct
                'context': {
                    'active_id': self.id,
                    'from_start': True,
                    'workcenter_id': self.workcenter_id and self.workcenter_id.id or False,
                }
            }
    # def button_start_wiz(self):
    #     self.ensure_one()
    #     if not self.timer_id:
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'name': _("Enter time"),
    #             'view_mode': 'form',
    #             'res_model': 'extra.time',
    #             'views': [(False, 'form')],
    #             'target': 'new',
    #             'context': {
    #                 'active_id': self.id,
    #                 'from_start': True,
    #                 'workcenter_id': self.workcenter_id and self.workcenter_id.id or False,
    #                 }
    #             }
    #     else:
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'name': _("Enter time"),
    #             'view_mode': 'form',
    #             'res_model': 'extra.time',
    #             'views': [(False, 'form')],
    #             'target': 'new',
    #             'res_id': self.timer_id,
    #             'context': {
    #                 'active_id': self.id,
    #                 'from_start': True,
    #                 'workcenter_id': self.workcenter_id and self.workcenter_id.id or False,
    #             }
    #         }
            
    def action_open_operation_description(self):
        """
        Action open operation description
        """
        if not self.operation_id:
            raise UserError("No Operation selected.")

        view_id = self.env.ref('mrp_enhancement.work_operation_sheet_view_form').id
        res_id = self.operation_id.id
        return {
            'type': 'ir.actions.act_window',
            'name': _("Operation Description"),
            'view_mode': 'form',
            'res_model': 'mrp.routing.workcenter',
            'views': [(view_id, 'form')],
            'target': 'new',
            'res_id': res_id
        }

    # def button_stop_wiz(self):
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': _("Enter time"),
    #         'view_mode': 'form',
    #         'res_model': 'extra.time',
    #         'views': [(False, 'form')],
    #         'target': 'new',
    #         'context': {
    #             'active_id': self.id,
    #             'from_done': True,
    #             'workcenter_id': self.workcenter_id and self.workcenter_id.id or False,
    #             }
    #         }

    def button_stop_wiz(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Roll Details"),
            'view_mode': 'form',
            'res_model': 'roll.lines',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'active_id': self.id,
                'from_done': True,
                'workcenter_id': self.workcenter_id and self.workcenter_id.id or False,
            }
        }

    def button_pending_wiz(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Roll Details"),
            'view_mode': 'form',
            'res_model': 'roll.lines',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'active_id': self.id,
                'workcenter_id': self.workcenter_id and self.workcenter_id.id or False,
            }
        }

    def action_reset_to_ready(self):
        """
        Reset the current workorder state from 'done' to 'ready'
        """
        for workorder in self:
            if workorder.state == 'done':
                workorder.state = 'ready'
            else:
                raise UserError(_("Workorder is not in 'done' state."))

    # Note: override the default method to set the user in the time tracking [time_ids]
    def end_previous(self, doall=False):
        """
        @param: doall:  This will close all open timelines on the open work orders when doall = True, otherwise
        only the one of the current user
        """
        # TDE CLEANME
        timeline_obj = self.env['mrp.workcenter.productivity']
        domain = [('workorder_id', 'in', self.ids), ('date_end', '=', False)]
        if not doall:
            domain.append(('user_id', '=', self.env.user.id))
        not_productive_timelines = timeline_obj.browse()
        for timeline in timeline_obj.search(domain, limit=None if doall else 1):
            wo = timeline.workorder_id
            if wo.duration_expected <= wo.duration:
                if timeline.loss_type == 'productive':
                    not_productive_timelines += timeline
                timeline.write({'date_end': fields.Datetime.now()})
            else:
                maxdate = fields.Datetime.from_string(timeline.date_start) + relativedelta(minutes=wo.duration_expected - wo.duration)
                enddate = datetime.now()
                if maxdate > enddate:
                    timeline.write({'date_end': enddate})
                    _logger.info("ENDDDATE 1111'%s'",enddate)
                else:
                    timeline.write({'date_end': maxdate})
                    not_productive_timelines += timeline.copy({'date_start': maxdate, 'date_end': enddate})
            # Added
            timeline.user_id = self._context.get('stop_user') if 'stop_user' in self._context else self.env.user.id
            timeline.x_yards_in = self._context.get('yds_in') if 'yds_in' in self._context else 0
            timeline.x_yards_out = self._context.get('yds_out') if 'yds_out' in self._context else 0
            timeline.roll_id = self._context.get('roll_id') if 'roll_id' in self._context else False
            timeline.quantity = self._context.get('quantity') if 'quantity' in self._context else 0
        # create time line if not exist
        if self._context.get('roll_rec'):
            roll_rec = self._context.get('roll_rec')
            if len(roll_rec.ids) > 1:
                for roll in roll_rec:
                    d = []
                    d.append(('roll_id', '=', roll.id))
                    time_rec = timeline_obj.search(d, limit=None if doall else 1)
                    if not time_rec:
                        new_timeline_rec = self.env['mrp.workcenter.productivity'].create(
                            self._prepare_timeline_vals(self.duration, datetime.now())
                        )
                        wo = new_timeline_rec.workorder_id
                        if wo.duration_expected <= wo.duration:
                            if new_timeline_rec.loss_type == 'productive':
                                not_productive_timelines += new_timeline_rec
                            new_timeline_rec.write({'date_end': fields.Datetime.now()})
                        else:
                            maxdate = fields.Datetime.from_string(new_timeline_rec.date_start) + relativedelta(
                                minutes=wo.duration_expected - wo.duration)
                            enddate = datetime.now()
                            if maxdate > enddate:
                                _logger.info("ENDDDATE22222 '%s'",enddate)
                                new_timeline_rec.write({'date_end': enddate})
                            else:
                                new_timeline_rec.write({'date_end': maxdate})
                                not_productive_timelines += new_timeline_rec.copy({'date_start': maxdate, 'date_end': enddate})
                        new_timeline_rec.write({
                            'user_id': self._context.get('stop_user') if 'stop_user' in self._context else self.env.user.id,
                            'x_yards_in': self._context.get('yds_in') if 'yds_in' in self._context else 0,
                            'x_yards_out': self._context.get('yds_out') if 'yds_out' in self._context else 0,
                            'roll_id': roll.id,
                            'quantity': roll.quantity
                        })
        if not_productive_timelines:
            loss_id = self.env['mrp.workcenter.productivity.loss'].search([('loss_type', '=', 'performance')], limit=1)
            if not len(loss_id):
                raise UserError(_("You need to define at least one unactive productivity loss in the category 'Performance'. Create one from the Manufacturing app, menu: Configuration / Productivity Losses."))
            not_productive_timelines.write({'loss_id': loss_id.id})
        return True

    def update_total_produce_quantity(self):
        """
        Update the Total Produce Quantity after creating/adding final roll ids
        """
        if self.roll_line_ids:
            self.total_produce_quantity += sum(self.roll_line_ids.mapped('quantity'))
        elif self.final_roll_line_ids:
            self.total_produce_quantity += sum(self.final_roll_line_ids.mapped('total_qty'))
        # Update the MO qty
        self.production_id.product_qty = sum(self.final_roll_line_ids.mapped('yards_qty'))
        return True

    def update_qty_producing(self):
        """
        Update the MO quantity
        """
        self.production_id.qty_producing += self.total_produce_quantity
        return True
