# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def action_recalculate_qty_done_from_customer_qty(self):
        for line in self.move_line_ids_without_package:
            if not line.customer_qty:
                continue
            if line.move_id and line.move_id.production_id:
                continue
            production = line._get_production_for_inverse()
            if not production:
                continue
            yards = line._compute_yards_from_customer_qty(
                line.customer_qty, production)
            _logger.info(
                "[GTS bulk recalc] line.id=%s lot=%s customer_qty=%s -> qty_done=%s",
                line.id,
                line.lot_id.name if line.lot_id else None,
                line.customer_qty, yards,
            )
            line.qty_done = yards