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

    @api.depends('quantity', 'lot_id', 'lot_id.customer_qty')
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
            if chain_line and chain_line.qty_done:
                ratio = quant.quantity / chain_line.qty_done
                quant.customer_qty = chain_line.customer_qty * ratio
                quant.x_customer_uom_id = chain_line.x_customer_uom_id
                continue

            # No move line was ever stamped with a non-zero customer_qty for
            # this lot (e.g. the delivery-picking sync in the production
            # wizard aborted because no sale order or more/less than one
            # matching picking was found). The lot itself is always stamped
            # with customer_qty at production time regardless of that sync,
            # so fall back to it and resolve the UOM from any move line
            # linked to the lot.
            if not quant.lot_id or not quant.lot_id.customer_qty:
                quant.customer_qty = 0.0
                quant.x_customer_uom_id = False
                continue

            any_line = self.env['stock.move.line'].search([
                ('lot_id', '=', quant.lot_id.id),
            ], order='date desc, id desc', limit=1)
            _logger.info(
                "[GTS DEBUG] quant._compute_customer_qty fallback: quant.id=%s "
                "lot_id.customer_qty=%s any_line.id=%s any_line.x_customer_uom_id=%s",
                quant.id, quant.lot_id.customer_qty,
                any_line.id if any_line else None,
                any_line.x_customer_uom_id.name if any_line and any_line.x_customer_uom_id else None,
            )
            quant.customer_qty = quant.lot_id.customer_qty
            quant.x_customer_uom_id = any_line.x_customer_uom_id if any_line else False