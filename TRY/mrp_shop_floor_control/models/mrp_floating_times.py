# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MrpFloatingTimes(models.Model):
    _name = "mrp.floating.times"
    _description = "MRP Floating Times"


    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', required=True, domain="[('manufacture_to_resupply', '=', 'True')]")
    mrp_release_time = fields.Float("Release Time", default=1.0)
    mrp_ftbp_time = fields.Float("Floating Time Before Production", default=1.0)
    mrp_ftap_time = fields.Float("Floating Time After Production", default=1.0)
    mrp_operations_first = fields.Integer("0-10000 yds")
    mrp_operations_second = fields.Integer("10000-25000 yds")
    mrp_operations_third = fields.Integer("25000-50000 yds")
    mrp_operations_fourth = fields.Integer("50000-100000 yds")
    mrp_operations_fifth = fields.Integer(">100000 yds")

    @api.constrains('warehouse_id')
    def _check_same_warehouse(self):
        for record in self:
            ft_ids = self.env['mrp.floating.times'].search([('warehouse_id', '=', record.warehouse_id.id)])
            if len(ft_ids) > 1:
                raise UserError(_('Another Floating Times record exists in the same warehouse: %s')% record.warehouse_id.name)
        return True


class MrpProduction(models.Model):
    _inherit = 'mrp.production'


    def action_confirm(self):
        res = super().action_confirm()
        for production in self:
            floating_times_id = self.env['mrp.floating.times'].search([('warehouse_id', '=', production.picking_type_id.warehouse_id.id)])
            if not floating_times_id:
                raise UserError(_('Floating Times record has not been created yet for the warehouse: %s')% production.picking_type_id.warehouse_id.name)
        return res