# -*- coding: utf-8 -*-
# Extension on mrp.production to support the Rolls smart button on the MO form.
# Goes in mrp_shop_floor_control/models/mrp_production_roll_ext.py

from odoo import models, fields, api


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    roll_count = fields.Integer(
        string='Roll Count',
        compute='_compute_mo_roll_count',
        help="Total number of rolls produced across all workorders of this MO.",
    )

    def _compute_mo_roll_count(self):
        for production in self:
            roll_ids = set()
            for wo in production.workorder_ids:
                for line in wo.roll_line_ids:
                    if line.roll_id:
                        roll_ids.add(line.roll_id.id)
            production.roll_count = len(roll_ids)

    def action_view_mo_rolls(self):
        """Smart button — open all rolls across all workorders of this MO."""
        self.ensure_one()
        roll_ids = set()
        for wo in self.workorder_ids:
            for line in wo.roll_line_ids:
                if line.roll_id:
                    roll_ids.add(line.roll_id.id)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rolls — %s' % (self.name or ''),
            'res_model': 'mrp.production.roll',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', list(roll_ids))],
        }