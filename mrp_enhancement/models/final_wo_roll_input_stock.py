# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
import logging

_logger = logging.getLogger(__name__)


class FinalWoRollInputStock(models.Model):
    """Stock handling for input rolls of a Final Yield line.

    Two cases, decided per input line (same rule as the roll lines of the
    other workorders, see mrp_shop_floor_control):

    * The roll's lot is a BOM component of this workorder's operation (a raw
      roll): the consumed quantity is recorded as ``qty_done`` on the lot's
      line of THAT operation's raw move of the MO. No separate stock move is
      posted: the stock leaves, and the cost reaches the finished product,
      when the raw move is completed (early consumption / MO done). Two BOM
      lines of the same product (one per operation) each keep their own
      quantity.
    * Otherwise (a WIP roll made by an earlier workorder): consumption is a
      stock move of its own, workcenter location -> production location,
      corrected by posting the difference. Moves carry
      ``x_final_roll_input_id`` so several lots on one Final Yield line are
      told apart.

    The parent final.wo.roll skips lines that have input lines, so nothing is
    posted twice.
    """
    _inherit = 'final.wo.roll.input'

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec._sync_input_roll_stock(rec._get_input_roll_lot())
        recs._sync_raw_pairs(recs._get_raw_pairs())
        return recs

    def write(self, vals):
        # A changed input roll must also release the old roll's raw move.
        old_pairs = self._get_raw_pairs() if 'previous_roll_id' in vals else []
        res = super().write(vals)
        if 'consumed_qty' in vals or 'previous_roll_id' in vals:
            for rec in self:
                rec._sync_input_roll_stock(rec._get_input_roll_lot())
            self._sync_raw_pairs(old_pairs + self._get_raw_pairs())
        return res

    def unlink(self):
        pairs = self._get_raw_pairs()
        # Give the stock back before the line (and its consumption) is gone.
        self._sync_input_roll_stock()
        res = super().unlink()
        # The raw move total no longer includes the deleted lines.
        self._sync_raw_pairs(pairs)
        return res

    def _get_input_roll_lot(self):
        """Lot of this line's input roll, falling back to a lookup by name
        when the roll has no lot_id set."""
        self.ensure_one()
        roll = self.previous_roll_id.roll_id
        if not roll:
            return self.env['stock.production.lot']
        lot = roll.lot_id
        if not lot and roll.name:
            lot = self.env['stock.production.lot'].search([
                ('name', '=', roll.name),
                ('company_id', '=', self.workorder_id.company_id.id),
            ], limit=1)
        return lot

    # ── raw roll: recorded on the MO component move ───────────────────────

    def _get_raw_move(self, lot=None):
        """MO raw move of this workorder's operation that consumes the
        roll's lot as a BOM component; empty for a WIP roll."""
        self.ensure_one()
        lot = lot or self._get_input_roll_lot()
        workorder = self.workorder_id
        if not lot or not workorder:
            return self.env['stock.move']
        candidates = self.env['mrp.wo.roll.line']._get_component_moves_for_workorder(workorder)
        return candidates.filtered(
            lambda m: m.product_id == lot.product_id and m.state != 'cancel')[:1]

    def _get_raw_pairs(self):
        """[(workorder, lot, raw_move)] for the lines booked on a raw move."""
        pairs, seen = [], set()
        for line in self:
            lot = line._get_input_roll_lot()
            raw_move = line._get_raw_move(lot)
            if raw_move and (line.workorder_id.id, lot.id) not in seen:
                seen.add((line.workorder_id.id, lot.id))
                pairs.append((line.workorder_id, lot, raw_move))
        return pairs

    @api.model
    def _sync_raw_pairs(self, pairs):
        """Like the standalone sync this never stops an operator from
        saving: a problem is logged and posted on the MO, and the next save
        retries (the target is always recomputed from the input lines)."""
        for workorder, lot, raw_move in pairs:
            try:
                with self.env.cr.savepoint():
                    self._sync_raw_booking(workorder, lot, raw_move)
            except Exception as err:  # noqa: BLE001
                _logger.exception(
                    "FINAL ROLL INPUT RAW: WO=%s lot=%s failed", workorder.id, lot.name)
                production = workorder.production_id
                if production:
                    production.sudo().message_post(body=_(
                        "Consumption of final roll %(roll)s was not recorded on "
                        "the component line: %(err)s. It will be retried the next "
                        "time the consumed quantity is saved.") % {
                        'roll': lot.name,
                        'err': getattr(err, 'name', False) or str(err),
                    })

    @api.model
    def _sync_raw_booking(self, workorder, lot, raw_move):
        """Make the done quantity of ``lot`` on ``raw_move`` equal to what
        this workorder's input lines consume of it. Only the move of this
        workorder's operation is touched."""
        rounding = lot.product_id.uom_id.rounding
        lines = self.sudo().search([('workorder_id', '=', workorder.id)]).filtered(
            lambda l: l._get_input_roll_lot() == lot)
        target = sum(lines.mapped('consumed_qty'))
        move_lines = raw_move.sudo().move_line_ids.filtered(
            lambda ml: ml.lot_id == lot).sorted('id')
        diff = target - sum(move_lines.mapped('qty_done'))
        if float_is_zero(diff, precision_rounding=rounding):
            return
        if diff > 0 and move_lines:
            last = move_lines[-1]
            last.write({'qty_done': last.qty_done + diff})
        elif diff > 0:
            self.env['stock.move.line'].sudo().create({
                'move_id': raw_move.id,
                'picking_id': raw_move.picking_id.id,
                'product_id': lot.product_id.id,
                'product_uom_id': raw_move.product_uom.id,
                'location_id': raw_move.location_id.id,
                'location_dest_id': raw_move.location_dest_id.id,
                'lot_id': lot.id,
                'product_uom_qty': 0.0,  # never reserved
                'qty_done': diff,
                'company_id': raw_move.company_id.id,
            })
        else:
            remaining = -diff
            for ml in move_lines.sorted('id', reverse=True):
                take = min(ml.qty_done, remaining)
                if take:
                    ml.write({'qty_done': ml.qty_done - take})
                    remaining -= take
                if float_is_zero(remaining, precision_rounding=rounding):
                    break
        _logger.info(
            "FINAL ROLL INPUT RAW: WO=%s move=%s lot=%s target=%s diff=%s",
            workorder.name, raw_move.id, lot.name, target, diff)

    # ── WIP roll: stock move of its own ───────────────────────────────────

    def _get_posted_input_roll_qty(self):
        """Net quantity already moved out of stock for this line, per lot:
        consume moves count positive, return moves negative."""
        self.ensure_one()
        posted = defaultdict(float)
        if not self.id:
            return posted
        moves = self.env['stock.move'].sudo().search([
            ('x_final_roll_input_id', '=', self.id),
            ('state', '=', 'done'),
        ])
        for move in moves:
            sign = 1.0 if move.location_dest_id.usage == 'production' else -1.0
            for ml in move.move_line_ids:
                if ml.lot_id:
                    posted[ml.lot_id] += sign * ml.qty_done
        return posted

    def _post_input_roll_move(self, lot, qty, src_loc, dest_loc):
        self.ensure_one()
        product = lot.product_id
        workorder = self.workorder_id
        production = workorder.production_id
        move = self.env['stock.move'].sudo().create({
            'name': _('Final roll %s: %s') % (
                lot.name, workorder.workcenter_id.name or ''),
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': qty,
            'location_id': src_loc.id,
            'location_dest_id': dest_loc.id,
            'company_id': workorder.company_id.id,
            'origin': production.name,
            'x_final_roll_input_id': self.id,
            'move_line_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'qty_done': qty,
                'lot_id': lot.id,
                'location_id': src_loc.id,
                'location_dest_id': dest_loc.id,
                'company_id': workorder.company_id.id,
            })],
        })
        move._action_confirm(merge=False)
        move._action_done()
        _logger.info(
            "FINAL ROLL INPUT STOCK: MO=%s WO=%s lot=%s qty=%s %s -> %s (move %s)",
            production.name, workorder.name, lot.name, qty,
            src_loc.complete_name, dest_loc.complete_name, move.id,
        )
        return move

    def _sync_input_roll_stock(self, lot=None):
        """Make stock reflect this line's consumed quantity of ``lot`` as a
        stock move of its own (WIP rolls).

        A raw roll is recorded on the MO raw move instead (see
        ``_sync_raw_booking``): for it the target here is 0, which also
        returns a standalone move posted for the line earlier. Without
        ``lot`` everything posted for the line is returned (line deleted,
        input roll removed or changed).

        Like the parent sync this never stops an operator from saving: a
        stock problem is logged and posted on the MO, and the next save
        retries (the quantity to post is always target minus already posted).
        """
        for line in self:
            posted = line._get_posted_input_roll_qty()
            raw_move = line._get_raw_move(lot) if lot else self.env['stock.move']
            targets = {lot: line.consumed_qty or 0.0} if (lot and not raw_move) else {}
            for posted_lot in posted:
                targets.setdefault(posted_lot, 0.0)

            for target_lot, target in targets.items():
                delta = target - posted.get(target_lot, 0.0)
                try:
                    with self.env.cr.savepoint():
                        line._post_input_roll_delta(target_lot, delta)
                except Exception as err:  # noqa: BLE001
                    _logger.exception(
                        "FINAL ROLL INPUT STOCK: line=%s lot=%s delta=%s failed",
                        line.id, target_lot.name, delta,
                    )
                    production = line.workorder_id.production_id
                    if production:
                        production.sudo().message_post(body=_(
                            "Stock for final roll %(roll)s was not updated "
                            "(%(qty)s): %(err)s. It will be retried the "
                            "next time the consumed quantity is saved.") % {
                            'roll': target_lot.name, 'qty': delta,
                            'err': getattr(err, 'name', False) or str(err),
                        })

    def _post_input_roll_delta(self, lot, delta):
        """Post the consume (delta > 0) or return (delta < 0) move."""
        self.ensure_one()
        product = lot.product_id
        rounding = product.uom_id.rounding
        if float_compare(delta, 0.0, precision_rounding=rounding) == 0:
            return

        wc_loc = self.workorder_id.workcenter_id.location_id
        prod_loc = self.final_roll_id._get_final_roll_production_location(product)
        if not wc_loc or not prod_loc:
            _logger.warning(
                "FINAL ROLL INPUT STOCK: line=%s lot=%s - missing workcenter "
                "or production location, skipping", self.id, lot.name)
            return

        if delta > 0:
            available = self.env['stock.quant'].sudo()._get_available_quantity(
                product, wc_loc, lot_id=lot, strict=True)
            if float_compare(available, delta, precision_rounding=rounding) < 0:
                raise UserError(_(
                    "only %(avail)s available at %(loc)s; make sure the "
                    "transfer of this roll to the work center is validated"
                ) % {'avail': available, 'loc': wc_loc.complete_name})
            self._post_input_roll_move(lot, delta, wc_loc, prod_loc)
        else:
            # Return to where the roll was originally consumed from.
            consumed_from = self.env['stock.move'].sudo().search([
                ('x_final_roll_input_id', '=', self.id),
                ('state', '=', 'done'),
                ('location_dest_id.usage', '=', 'production'),
                ('move_line_ids.lot_id', '=', lot.id),
            ], order='id desc', limit=1).location_id
            self._post_input_roll_move(
                lot, -delta, prod_loc, consumed_from or wc_loc)
