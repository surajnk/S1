# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    mpp_id = fields.Many2one('mrp.production.plan', 'MPP ID')


    def action_cancel(self):
        res = super().action_cancel()
        for production in self:
            if production.mpp_id:
                mpp_capacity_ids = self.env['mrp.mpp.capacity'].search([('MPP_item', '=', production.mpp_id.name )])
                mpp_capacity_ids.write({'active': False})
        return res

    def button_mark_done(self):
        res = super().button_mark_done()
        for production in self:
            if production.mpp_id:
                mpp_capacity_ids = self.env['mrp.mpp.capacity'].search([('MPP_item', '=', production.mpp_id.name )])
                mpp_capacity_ids.write({'active': False})
        return res