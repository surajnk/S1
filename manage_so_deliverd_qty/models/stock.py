# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class StockMove(models.Model):
    _inherit = "stock.move"

    cust_qty = fields.Float(string='Customer Qty', copy=0)

    def open_on_hand_qtyst(self):
        """
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Quantity',
            'view_mode': 'tree,form',
            'res_model': 'stock.quant',
            'domain': [['product_id', '=', self.product_id.id]],
            'context': {'default_product_id': self.product_id.id},
            'target': 'new'
        }