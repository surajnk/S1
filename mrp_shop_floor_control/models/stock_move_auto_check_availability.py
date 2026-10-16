# -*- coding: utf-8 -*-
from odoo import models, _
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder=cancel_backorder)
        self._trigger_check_availability_after_return()
        self._consume_raw_moves_on_return()
        return res

    def _consume_raw_moves_on_return(self):
        """Complete the MO raw moves holding recorded consumption once the
        return of the Pick Components transfer feeding them is validated.

        Only with ``mrp_shop_floor_control.consume_on_return`` (and
        ``early_raw_consumption``). Per raw
        move: only raw moves fed by a returned transfer move and with
        ``qty_done`` recorded on their lines. The unconsumed remainder is
        cancelled (the rest went back to stock); over-consumption becomes
        the usual extra move. Never blocks the return from validating.
        """
        # The cost of moves completed here is added to the finished product
        # by the early-consumption cost handling, so both must be on.
        if not (self._consume_on_return_enabled()
                and self._early_raw_consumption_enabled()):
            return
        return_moves = self.filtered(
            lambda m: m.origin_returned_move_id and m.state == 'done')
        if not return_moves:
            return

        raw_moves = self.env['stock.move']
        for move in return_moves:
            raw_moves |= move.origin_returned_move_id.move_dest_ids.filtered(
                lambda m: m.raw_material_production_id
                and m.state not in ('done', 'cancel')
                and any(ml.qty_done > 0 for ml in m.move_line_ids))
        if not raw_moves:
            return

        raw_moves._consume_recorded_raw_moves()

    def _consume_recorded_raw_moves(self, raise_errors=False):
        """Complete these MO raw moves with ``_action_done(cancel_backorder=
        True)`` and flag the newly done ones ``x_early_consumed`` so their
        cost reaches the finished product. Per MO, inside a savepoint.

        A failure is posted on the MO and swallowed, unless ``raise_errors``
        (used by the "Consume Now" button so the user sees the reason).
        """
        Move = self.env['stock.move'].sudo()
        for production in self.mapped('raw_material_production_id'):
            production_moves = self.filtered(
                lambda m: m.raw_material_production_id == production)
            domain = [
                ('raw_material_production_id', '=', production.id),
                ('state', '=', 'done'),
            ]
            try:
                with self.env.cr.savepoint():
                    done_before = Move.search(domain)
                    production_moves._action_done(cancel_backorder=True)
                    (Move.search(domain) - done_before).write(
                        {'x_early_consumed': True})
                _logger.info(
                    "CONSUME RECORDED: MO=%s raw moves %s completed",
                    production.name, production_moves.ids)
            except Exception as err:  # noqa: BLE001
                if raise_errors:
                    raise
                _logger.exception(
                    "CONSUME RECORDED: completing raw moves %s of MO %s "
                    "failed", production_moves.ids, production.name)
                production.sudo().message_post(body=_(
                    "The consumed material was not taken out of stock when "
                    "the return was validated: %(err)s. It will be consumed "
                    "when the MO is marked done.") % {
                    'err': getattr(err, 'name', False) or str(err)})

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