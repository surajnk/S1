# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
import logging

_logger = logging.getLogger(__name__)


class MrpWoRollLineConsumptionSync(models.Model):
    _inherit = 'mrp.wo.roll.line'

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._sync_raw_move_consumed()
        return rec

    def write(self, vals):
        # With early raw consumption, an input roll that is replaced must
        # have its consumption reduced as well.
        old_pairs = self._get_early_raw_pairs() if 'prev_roll_id' in vals else []
        res = super().write(vals)
        if 'consumed_qty' in vals or 'prev_roll_id' in vals:
            self._sync_raw_move_consumed()
        if old_pairs:
            self._resync_early_raw_pairs(old_pairs)
        return res

    def unlink(self):
        # Give the stock back before the line (and its consumption) is gone.
        self._sync_wip_roll_stock()
        pairs = self._get_early_raw_pairs()
        res = super().unlink()
        if pairs:
            self.env['mrp.wo.roll.line']._resync_early_raw_pairs(pairs)
        return res

    def _get_early_raw_pairs(self):
        """(input roll, production) pairs whose raw consumption may change."""
        if not self.env['stock.move']._early_raw_consumption_enabled():
            return []
        pairs = []
        for rec in self:
            production = rec.workorder_id.production_id
            if rec.prev_roll_id and production and (rec.prev_roll_id, production) not in pairs:
                pairs.append((rec.prev_roll_id, production))
        return pairs

    def _resync_early_raw_pairs(self, pairs):
        """Re-align the raw move quantity of each (roll, production) pair
        with what the remaining roll lines say was consumed."""
        for roll, production in pairs:
            lot = roll.lot_id
            if not lot and roll.name:
                lot = self.env['stock.production.lot'].search([
                    ('name', '=', roll.name),
                    ('company_id', '=', production.company_id.id),
                ], limit=1)
            if not lot or lot.product_id == production.product_id:
                continue  # WIP rolls are handled by _sync_wip_roll_stock
            total_consumed = sum(self.env['mrp.wo.roll.line'].search([
                ('prev_roll_id', '=', roll.id),
                ('workorder_id.production_id', '=', production.id),
            ]).mapped('consumed_qty'))
            self._sync_raw_move_early(production, lot, False, total_consumed)

    # ── WIP roll stock handling ───────────────────────────────────────────
    # A WIP roll is a lot of the finished product, so there is no raw
    # component move to carry its consumption.  Consumption of an input roll
    # is therefore posted here as its own stock move: workcenter location ->
    # production location.  Corrections post the difference (a further
    # consume move, or a return move), always per roll line and lot.

    def _get_posted_wip_roll_qty(self):
        """Net quantity already moved out of stock for this line, per lot.

        Returns ``{lot: qty}`` where consume moves count positive and
        return moves negative.
        """
        self.ensure_one()
        posted = defaultdict(float)
        if not self.id:
            return posted
        moves = self.env['stock.move'].sudo().search([
            ('x_roll_line_id', '=', self.id),
            ('state', '=', 'done'),
        ])
        for move in moves:
            sign = 1.0 if move.location_dest_id.usage == 'production' else -1.0
            for ml in move.move_line_ids:
                if ml.lot_id:
                    posted[ml.lot_id] += sign * ml.qty_done
        return posted

    def _get_wip_roll_production_location(self, product):
        location = product.property_stock_production
        if not location:
            location = self.env['stock.location'].search([
                ('usage', '=', 'production'),
                ('company_id', 'in', [self.workorder_id.company_id.id, False]),
            ], limit=1)
        return location

    def _post_wip_roll_move(self, lot, qty, src_loc, dest_loc):
        self.ensure_one()
        product = lot.product_id
        production = self.workorder_id.production_id
        move = self.env['stock.move'].sudo().create({
            'name': _('WIP roll %s: %s') % (
                lot.name, self.workorder_id.workcenter_id.name or ''),
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': qty,
            'location_id': src_loc.id,
            'location_dest_id': dest_loc.id,
            'company_id': self.workorder_id.company_id.id,
            'origin': production.name,
            'x_roll_line_id': self.id,
            'move_line_ids': [(0, 0, {
                'product_id': product.id,
                'product_uom_id': product.uom_id.id,
                'qty_done': qty,
                'lot_id': lot.id,
                'location_id': src_loc.id,
                'location_dest_id': dest_loc.id,
                'company_id': self.workorder_id.company_id.id,
            })],
        })
        move._action_confirm(merge=False)
        move._action_done()
        _logger.info(
            "WIP ROLL STOCK: MO=%s WO=%s lot=%s qty=%s %s -> %s (move %s)",
            production.name, self.workorder_id.name, lot.name, qty,
            src_loc.complete_name, dest_loc.complete_name, move.id,
        )
        return move

    def _sync_wip_roll_stock(self, lot=None):
        """Make stock reflect this line's consumed quantity of ``lot``.

        Without ``lot`` everything posted for the line is returned (line
        deleted, input roll removed or changed).

        This must never stop an operator from saving the roll line: a stock
        problem is logged and posted on the MO, and the next save retries
        (the quantity to post is always target minus what is already posted).
        """
        for line in self:
            posted = line._get_posted_wip_roll_qty()
            targets = {lot: line.consumed_qty or 0.0} if lot else {}
            for posted_lot in posted:
                targets.setdefault(posted_lot, 0.0)

            for target_lot, target in targets.items():
                delta = target - posted.get(target_lot, 0.0)
                try:
                    with self.env.cr.savepoint():
                        line._post_wip_roll_delta(target_lot, delta)
                except Exception as err:  # noqa: BLE001
                    _logger.exception(
                        "WIP ROLL STOCK: line=%s lot=%s delta=%s failed",
                        line.id, target_lot.name, delta,
                    )
                    production = line.workorder_id.production_id
                    if production:
                        production.sudo().message_post(body=_(
                            "Stock for WIP roll %(roll)s was not updated "
                            "(%(qty)s): %(err)s. It will be retried the next "
                            "time the consumed quantity is saved.") % {
                            'roll': target_lot.name, 'qty': delta,
                            'err': getattr(err, 'name', False) or str(err),
                        })

    def _post_wip_roll_delta(self, lot, delta):
        """Post the consume (delta > 0) or return (delta < 0) move."""
        self.ensure_one()
        product = lot.product_id
        rounding = product.uom_id.rounding
        if float_compare(delta, 0.0, precision_rounding=rounding) == 0:
            return

        wc_loc = self.workorder_id.workcenter_id.location_id
        prod_loc = self._get_wip_roll_production_location(product)
        if not wc_loc or not prod_loc:
            _logger.warning(
                "WIP ROLL STOCK: line=%s lot=%s - missing workcenter "
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
            self._post_wip_roll_move(lot, delta, wc_loc, prod_loc)
        else:
            # Return to where the roll was originally consumed from.
            consumed_from = self.env['stock.move'].sudo().search([
                ('x_roll_line_id', '=', self.id),
                ('state', '=', 'done'),
                ('location_dest_id.usage', '=', 'production'),
                ('move_line_ids.lot_id', '=', lot.id),
            ], order='id desc', limit=1).location_id
            self._post_wip_roll_move(
                lot, -delta, prod_loc, consumed_from or wc_loc)

    def _sync_raw_move_early(self, production, lot, raw_move, total_consumed):
        """Early raw consumption (``mrp_shop_floor_control.early_raw_consumption``).

        Keep the lot's done quantity on the MO's raw move lines equal to
        ``total_consumed`` and complete the raw move, so the stock leaves the
        work center when the quantity is saved. Once a move is done, further
        edits of ``qty_done`` are corrected by Odoo itself (quants, valuation
        layer and journal entry).
        """
        product = lot.product_id
        rounding = product.uom_id.rounding
        Move = self.env['stock.move'].sudo()

        # Completing a move can split it (extra / backorder moves), so the
        # lot's lines may sit on several raw moves of the product.
        moves = Move.search([
            ('raw_material_production_id', '=', production.id),
            ('product_id', '=', product.id),
            ('state', '!=', 'cancel'),
        ])
        lines = self.env['stock.move.line'].sudo().search([
            ('move_id', 'in', moves.ids),
            ('lot_id', '=', lot.id),
        ], order='id')
        diff = total_consumed - sum(lines.mapped('qty_done'))

        if float_is_zero(diff, precision_rounding=rounding):
            pass
        elif diff > 0 and lines:
            last = lines[-1]
            last.with_context(skip_remained_update=True).write({
                'qty_done': last.qty_done + diff,
            })
        elif diff > 0:
            target = moves.filtered(lambda m: m.state == 'done')[:1] or raw_move
            if not target:
                return
            self.env['stock.move.line'].sudo().create({
                'move_id': target.id,
                'picking_id': target.picking_id.id,
                'product_id': product.id,
                'product_uom_id': target.product_uom.id,
                'location_id': target.location_id.id,
                'location_dest_id': target.location_dest_id.id,
                'lot_id': lot.id,
                'product_uom_qty': 0.0,  # never reserved
                'qty_done': diff,
                'company_id': target.company_id.id,
            })
        else:
            remaining = -diff
            for ml in lines.sorted('id', reverse=True):
                take = min(ml.qty_done, remaining)
                if take:
                    ml.with_context(skip_remained_update=True).write({
                        'qty_done': ml.qty_done - take,
                    })
                    remaining -= take
                if float_is_zero(remaining, precision_rounding=rounding):
                    break
        _logger.info(
            "RAW CONSUMED SYNC (early): MO=%s lot=%s total_consumed=%s diff=%s",
            production.name, lot.name, total_consumed, diff)

        # Complete the raw move(s) holding the consumption, once.
        open_moves = Move.search([
            ('raw_material_production_id', '=', production.id),
            ('product_id', '=', product.id),
            ('state', 'not in', ('done', 'cancel')),
        ]).filtered(lambda m: any(
            ml.lot_id == lot and ml.qty_done > 0 for ml in m.move_line_ids))
        if not open_moves:
            return
        try:
            with self.env.cr.savepoint():
                done_before = Move.search([
                    ('raw_material_production_id', '=', production.id),
                    ('state', '=', 'done'),
                ])
                open_moves._action_done()
                newly_done = Move.search([
                    ('raw_material_production_id', '=', production.id),
                    ('state', '=', 'done'),
                ]) - done_before
                newly_done.write({'x_early_consumed': True})
        except Exception as err:  # noqa: BLE001
            _logger.exception(
                "RAW CONSUMED SYNC (early): completing raw move of %s for "
                "MO %s failed", product.display_name, production.name)
            production.sudo().message_post(body=_(
                "Raw material %(product)s lot %(lot)s was not taken out of "
                "stock when the consumption was saved: %(err)s. It will be "
                "consumed when the MO is marked done.") % {
                'product': product.display_name, 'lot': lot.name,
                'err': getattr(err, 'name', False) or str(err),
            })

    def _get_component_moves_for_workorder(self, workorder):

        moves = workorder.production_id.move_raw_ids

        if 'curr_comp' in moves._fields and 'component_workorder_ids' in moves._fields:
            tier1 = moves.filtered(
                lambda m: m.curr_comp and (workorder in m.component_workorder_ids)
            )
            if tier1:
                return tier1

        tier2 = moves.filtered(
            lambda m: m.x_comp_operation and
                      m.x_comp_operation.name == workorder.operation_id.name
        )
        if tier2:
            return tier2

        bom_lines = workorder.production_id.bom_id.bom_line_ids.filtered(
            lambda l: workorder.operation_id in l.workcenter_capacities
        )
        if bom_lines:
            tier3_products = bom_lines.mapped('product_id')
            return moves.filtered(lambda m: m.product_id in tier3_products)

        return moves

    def _sync_raw_move_consumed(self):
        for rec in self:
            if not rec.prev_roll_id or not rec.workorder_id:
                # Input roll removed: give back anything posted for the line.
                rec._sync_wip_roll_stock()
                continue

            production = rec.workorder_id.production_id
            if not production:
                continue
            lot = rec.prev_roll_id.lot_id
            if not lot and rec.prev_roll_id.name:
                lot = self.env['stock.production.lot'].search([
                    ('name', '=', rec.prev_roll_id.name),
                    ('company_id', '=', production.company_id.id),
                ], limit=1)
            if not lot:
                continue

            candidate_moves = self._get_component_moves_for_workorder(rec.workorder_id)
            raw_move = candidate_moves.filtered(
                lambda m: m.product_id == lot.product_id and m.state not in ('cancel',)
            )[:1]

            if not raw_move:
                # The input roll is a WIP roll (a lot of the finished
                # product), not a BOM component: move its stock directly.
                _logger.info(
                    "RAW CONSUMED SYNC: MO=%s WO=%s lot=%s product=%s - no "
                    "raw move, syncing WIP roll stock instead",
                    production.name, rec.workorder_id.name, lot.name,
                    lot.product_id.display_name,
                )
                if lot.product_id == production.product_id:
                    rec._sync_wip_roll_stock(lot)
                continue

            total_consumed = sum(
                self.env['mrp.wo.roll.line'].search([
                    ('prev_roll_id', '=', rec.prev_roll_id.id),
                    ('workorder_id.production_id', '=', production.id),
                ]).mapped('consumed_qty')
            )

            # total_consumed = sum(
            #     self.env['mrp.wo.roll.line'].search([
            #         ('prev_roll_id', '=', rec.prev_roll_id.id)
            #     ]).mapped('consumed_qty')
            # )

            if self.env['stock.move']._early_raw_consumption_enabled():
                rec._sync_raw_move_early(production, lot, raw_move, total_consumed)
                continue

            existing_line = raw_move.move_line_ids.filtered(lambda ml: ml.lot_id == lot)

            if existing_line:
                if existing_line[0].qty_done != total_consumed:
                    existing_line[0].with_context(skip_remained_update=True).write({
                        'qty_done': total_consumed,
                    })
                    _logger.info(
                        "RAW CONSUMED SYNC (update): MO=%s WO=%s lot=%s "
                        "qty_done set to %s",
                        production.name, rec.workorder_id.name, lot.name,
                        total_consumed,
                    )
            else:
                self.env['stock.move.line'].create({
                    'move_id': raw_move.id,
                    'picking_id': raw_move.picking_id.id,
                    'product_id': lot.product_id.id,
                    'product_uom_id': raw_move.product_uom.id,
                    'location_id': raw_move.location_id.id,
                    'location_dest_id': raw_move.location_dest_id.id,
                    'lot_id': lot.id,
                    'product_uom_qty': 0.0,  # never reserved
                    'qty_done': total_consumed,
                    'company_id': raw_move.company_id.id,
                })
                _logger.info(
                    "RAW CONSUMED SYNC (new line): MO=%s WO=%s lot=%s "
                    "qty_done=%s created under move=%s",
                    production.name, rec.workorder_id.name, lot.name,
                    total_consumed, raw_move.id,
                )