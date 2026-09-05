# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    customer_qty = fields.Float(
        string='Customer Qty', compute='_compute_customer_qty')
    x_customer_uom_id = fields.Many2one(
        'uom.uom', string='Customer UOM', compute='_compute_customer_qty')

    def _get_chain_line_for_quant(self):
        self.ensure_one()
        if not self.lot_id:
            return self.env['stock.move.line']
        chain_line = self.env['stock.move.line'].search([
            ('lot_id', '=', self.lot_id.id),
            ('customer_qty', '!=', 0),
        ], order='date desc, id desc', limit=1)
        return chain_line

    @api.depends('quantity', 'lot_id')
    def _compute_customer_qty(self):
        for quant in self:
            chain_line = quant._get_chain_line_for_quant()
            _logger.info(
                "[GTS DEBUG] quant._compute_customer_qty: quant.id=%s lot_id=%s "
                "quantity=%s chain_line.id=%s chain_line.qty_done=%s chain_line.customer_qty=%s",
                quant.id, quant.lot_id.id if quant.lot_id else None, quant.quantity,
                chain_line.id if chain_line else None,
                chain_line.qty_done if chain_line else None,
                chain_line.customer_qty if chain_line else None,
            )
            if not chain_line or not chain_line.qty_done:
                quant.customer_qty = 0.0
                quant.x_customer_uom_id = False
                continue
            ratio = quant.quantity / chain_line.qty_done
            quant.customer_qty = chain_line.customer_qty * ratio
            quant.x_customer_uom_id = chain_line.x_customer_uom_id