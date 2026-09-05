# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import UserError


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

    def _inverse_roll_line_ids(self):
        for workorder in self:
            #workorder.qty_produced = sum(workorder.roll_line_ids.mapped('quantity'))
            workorder.total_produce_quantity = sum(workorder.roll_line_ids.mapped('quantity'))

    def button_start_wiz(self):
        self.ensure_one()
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
                else:
                    timeline.write({'date_end': maxdate})
                    not_productive_timelines += timeline.copy({'date_start': maxdate, 'date_end': enddate})
            # Added
            timeline.user_id = self._context.get('stop_user') if 'stop_user' in self._context else self.env.user.id
            timeline.roll_id = self._context.get('roll_id') if 'roll_id' in self._context else False
            timeline.quantity = self._context.get('quantity') if 'quantity' in self._context else 0

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
