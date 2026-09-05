# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, SUPERUSER_ID


class MrpWorkCenter(models.Model):
    _inherit = 'mrp.workcenter'
    _description = 'Work Center'

    user_ids = fields.Many2many('res.users', 'mrp_workcenter_users_rel', string = 'WC Users')

    @api.model
    def create(self, values):
        res = super().create(values)
        for user in res.user_ids:
            user.sudo().write({
                'workcenter_ids': [(6, 0, self.ids)]
            })
        return res

    def write(self, values):
        res = super().write(values)
        if values.get('user_ids'):
            for user in self.user_ids:
                user.write({
                    'workcenter_ids': [(4, self.id)]
                })
        mrp_wc_users = self.env['res.users'].search([]).filtered(lambda x: self.id in x.workcenter_ids.ids)
        for wc_user in mrp_wc_users:
            if wc_user.id not in self.user_ids.ids:
                wc_user.write({
                    'workcenter_ids': [(3, self.id)]
                })
        return res
