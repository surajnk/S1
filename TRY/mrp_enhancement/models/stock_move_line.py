# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, tools, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"


    @api.onchange('lot_name', 'lot_id')
    def _onchange_serial_number(self):
        res = super()._onchange_serial_number()
        if self.lot_id and self.lot_id.product_qty:
            self.qty_done = self.lot_id.product_qty
        return res


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    # Manage the lots based on the From location
    def _name_search(self, name, args = None, operator = 'ilike', limit = 100, name_get_uid = None):
        if self._context.get('product_from_detailed_operation') and self._context.get('from_location_id'):
            stockQuants = self.env['stock.quant'].sudo().search([
                ('product_id', '=', int(self._context.get('product_from_detailed_operation'))),
                ('location_id', '=', int(self._context.get('from_location_id'))),
            ])
            args = [('id', 'in', stockQuants.mapped('lot_id').ids or [])]
        return super(StockProductionLot, self)._name_search(name = name, args = args, operator = operator, limit = limit, name_get_uid = name_get_uid)