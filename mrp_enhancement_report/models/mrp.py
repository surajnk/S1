# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MrpProduction(models.Model):
    _inherit = 'mrp.production'
    _description = 'Work Center'

    shaded = fields.Boolean('Shaded')

    # def action_confirm(self):
    #     if self.workorder_ids:
    #         for workorder_id in self.workorder_ids:
    #             if not workorder_id.width or not workorder_id.trim:
    #                 raise ValidationError(_("Please insert width and trim for all workorders"))
    #     return super().action_confirm()

    # def button_plan(self):
    #     if self.workorder_ids:
    #         for workorder_id in self.workorder_ids:
    #             if not workorder_id.width or not workorder_id.trim:
    #                 raise ValidationError(_("Please insert width and trim for all workorders"))
    #     return super().button_plan()
