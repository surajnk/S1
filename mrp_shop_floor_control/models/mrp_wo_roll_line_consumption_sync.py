# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
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
        res = super().write(vals)
        if 'consumed_qty' in vals or 'prev_roll_id' in vals:
            self._sync_raw_move_consumed()
        return res

    def unlink(self):
        # Give the stock back before the line (and its consumption) is gone.
        self._sync_wip_roll_stock()
        return super().unlink()

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
        """
        for line in self:
            posted = line._get_posted_wip_roll_qty()
            targets = {lot: line.consumed_qty or 0.0} if lot else {}
            for posted_lot in posted:
                targets.setdefault(posted_lot, 0.0)

            for target_lot, target in targets.items():
                product = target_lot.product_id
                rounding = product.uom_id.rounding
                delta = target - posted.get(target_lot, 0.0)
                if float_compare(delta, 0.0, precision_rounding=rounding) == 0:
                    continue

                wc_loc = line.workorder_id.workcenter_id.location_id
                prod_loc = line._get_wip_roll_production_location(product)
                if not wc_loc or not prod_loc:
                    _logger.warning(
                        "WIP ROLL STOCK: line=%s lot=%s - missing workcenter "
                        "or production location, skipping",
                        line.id, target_lot.name,
                    )
                    continue

                if delta > 0:
                    available = self.env['stock.quant'].sudo()._get_available_quantity(
                        product, wc_loc, lot_id=target_lot, strict=True)
                    if float_compare(
                            available, delta, precision_rounding=rounding) < 0:
                        raise UserError(_(
                            "Cannot consume %(qty)s of roll %(roll)s: only "
                            "%(avail)s available at %(loc)s. Make sure the "
                            "transfer of this roll to the work center is "
                            "validated.") % {
                            'qty': delta, 'roll': target_lot.name,
                            'avail': available, 'loc': wc_loc.complete_name,
                        })
                    line._post_wip_roll_move(target_lot, delta, wc_loc, prod_loc)
                else:
                    # Return to where the roll was originally consumed from.
                    consumed_from = self.env['stock.move'].sudo().search([
                        ('x_roll_line_id', '=', line.id),
                        ('state', '=', 'done'),
                        ('location_dest_id.usage', '=', 'production'),
                        ('move_line_ids.lot_id', '=', target_lot.id),
                    ], order='id desc', limit=1).location_id
                    line._post_wip_roll_move(
                        target_lot, -delta, prod_loc, consumed_from or wc_loc)

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