# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.tools.float_utils import float_round
import logging

_logger = logging.getLogger(__name__)


class StockReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    @api.model
    def _prepare_stock_return_picking_line_vals_from_move(self, stock_move):
        vals = super()._prepare_stock_return_picking_line_vals_from_move(stock_move)

        early_vals = self._early_consumed_return_vals(stock_move, vals)
        if early_vals is not None:
            return early_vals

        raw_moves = stock_move.move_dest_ids.filtered(
            lambda m: m.raw_material_production_id and m.state not in ('done', 'cancel')
        )
        if not raw_moves:
            return vals

        reserved_already_subtracted = sum(
            raw_moves.mapped('move_line_ids').mapped('product_qty')
        )
        actual_consumed = sum(
            raw_moves.mapped('move_line_ids').mapped('qty_done')
        )
        correction = actual_consumed - reserved_already_subtracted

        if correction:
            new_qty = max(vals['quantity'] - correction, 0.0)
            new_qty = float_round(new_qty, precision_rounding=stock_move.product_uom.rounding)
            _logger.info(
                "RETURN DEFAULT QTY FIX: move=%s product=%s "
                "core_default=%s reserved_subtracted_by_core=%s "
                "actual_consumed=%s corrected=%s",
                stock_move.id, stock_move.product_id.display_name,
                vals['quantity'], reserved_already_subtracted,
                actual_consumed, new_qty,
            )
            vals['quantity'] = new_qty

        return vals

    @api.model
    def _early_consumed_return_vals(self, stock_move, vals):
        """Default return quantity when raw moves were completed early.

        Only active with ``mrp_shop_floor_control.early_raw_consumption``
        and when a raw move fed by this transfer is already done.

        Odoo subtracts a done raw move's own quantity, but consuming more
        than the demand splits an extra move that is not linked to the
        transfer, so the default came out too high. The returnable quantity
        is what was picked, minus what was already returned, minus what was
        actually consumed of the transfer's lots.
        """
        if not self.env['stock.move']._early_raw_consumption_enabled():
            return None
        dest_raw = stock_move.move_dest_ids.filtered(
            lambda m: m.raw_material_production_id and m.state != 'cancel')
        if not dest_raw.filtered(lambda m: m.state == 'done'):
            return None

        # What Odoo already subtracted for these raw moves.
        core_subtracted = 0.0
        for move in dest_raw:
            if move.state in ('partially_available', 'assigned'):
                core_subtracted += sum(move.move_line_ids.mapped('product_qty'))
            elif move.state == 'done':
                core_subtracted += move.product_qty

        # What was actually consumed of this transfer's lots, including the
        # extra / backorder raw moves created when a move is completed.
        raw_moves = self.env['stock.move'].search([
            ('raw_material_production_id', 'in',
             dest_raw.mapped('raw_material_production_id').ids),
            ('product_id', '=', stock_move.product_id.id),
            ('state', '!=', 'cancel'),
        ])
        lots = stock_move.move_line_ids.mapped('lot_id')
        lines = raw_moves.mapped('move_line_ids')
        if lots:
            lines = lines.filtered(lambda ml: ml.lot_id in lots)
        actual_consumed = sum(lines.mapped('qty_done'))

        new_qty = max(vals['quantity'] + core_subtracted - actual_consumed, 0.0)
        new_qty = float_round(
            new_qty, precision_rounding=stock_move.product_uom.rounding)
        _logger.info(
            "RETURN DEFAULT QTY FIX (early consumption): move=%s product=%s "
            "core_default=%s core_subtracted=%s actual_consumed=%s "
            "corrected=%s",
            stock_move.id, stock_move.product_id.display_name,
            vals['quantity'], core_subtracted, actual_consumed, new_qty,
        )
        vals['quantity'] = new_qty
        return vals
