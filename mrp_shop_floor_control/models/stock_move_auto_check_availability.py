# -*- coding: utf-8 -*-
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        self._trigger_check_availability_after_return()
        return res

    def _trigger_check_availability_after_return(self):
        return_moves = self.filtered(
            lambda m: m.origin_returned_move_id and m.state == 'done'
        )
        if not return_moves:
            return

        productions = self.env['mrp.production']
        for move in return_moves:
            original_move = move.origin_returned_move_id
            raw_moves = original_move.move_dest_ids.filtered(
                lambda m: m.raw_material_production_id
            )
            productions |= raw_moves.mapped('raw_material_production_id')

        if productions:
            _logger.info(
                "AUTO CHECK AVAILABILITY: triggering action_assign for "
                "MO(s) %s after return validated",
                productions.mapped('name'),
            )
            productions.action_assign()