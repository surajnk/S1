# -*- coding: utf-8 -*-
# Part of GeoTechnosoft. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    show_partial_produce = fields.Boolean(related='workcenter_id.show_partial_produce')

    # def open_produce_product(self):
    #     """
    #     Open Partially produce from work center
    #     """
    #     if self.production_id:
    #         total_produce = sum(self.final_roll_line_ids.mapped("yards_qty"))
    #         return self.production_id.open_produce_product()

    def open_produce_product(self):
        self.ensure_one()
        context = self.env.context.copy() or {}
        context['active_id'] = self.production_id.id
        context['active_model'] = 'mrp.production'
        action = self.production_id.open_produce_product()
        action['context'] = context
        return action

    # def _set_qty_producing(self):
    #     for workorder in self:
    #         if workorder.production_id.partial_qty_produced:
    #             workorder.production_id.qty_producing = workorder.qty_producing
    #             print ("1111111111111111111111111111")
    #             workorder.production_id._set_qty_producing()
    #         elif workorder.qty_producing != 0 and workorder.production_id.qty_producing != workorder.qty_producing:
    #             workorder.production_id.qty_producing = workorder.qty_producing
    #             print("22222222222222222222222222222")
    #             workorder.production_id._set_qty_producing()
