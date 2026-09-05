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