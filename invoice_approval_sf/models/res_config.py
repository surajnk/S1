# -*- coding: utf-8 -*-
##############################################################################
#
#    Shinefy Technologies Pvt. Ltd.
#    Copyright (C) 2022 Shinefy Technologies.
#    Author: Shinefy Technologies
#    
#    For Module Support : shinefytech@gmail.com  or Skype : shinefytech@gmail.com
#
##############################################################################

from odoo import api, fields, models, modules
import ast
from ast import literal_eval

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    inv_appr_ids = fields.Many2many('res.users', string="Bill Approvers")
    
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        with_user = self.env['ir.config_parameter'].sudo()
        inv_approvers = with_user.get_param('invoice_approval_sf.inv_appr_ids')
        if inv_approvers:
            res.update(
                inv_appr_ids=[(6, 0, ast.literal_eval(inv_approvers))],
                )
        return res

    def set_values(self):
        res = super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].sudo().set_param('invoice_approval_sf.inv_appr_ids', self.inv_appr_ids.ids)

        inv_approvers = self.inv_appr_ids.ids

        inv_ids = self.env['account.move'].search([])
        
        if inv_approvers:
            for inv in inv_ids:
                inv.inv_appr_ids = inv_approvers