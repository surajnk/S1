# -*- coding: utf-8 -*-

from collections import defaultdict

from odoo import models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
import logging

_logger = logging.getLogger(__name__)


class FinalWoRollInputStock(models.Model):
    """Stock handling for input rolls of a Final Yield line.

    Same behaviour as final.wo.roll's own sync (see
    final_wo_roll_consumption_sync.py) but per input line: consumption of an
    input roll is posted as its own stock move, workcenter location ->
    production location, and corrected by posting the difference. The moves
    carry ``x_final_roll_input_id``, so several lots on one Final Yield line
    are told apart and corrected independently.

    The parent final.wo.roll skips lines that have input lines, so nothing is
    posted twice.
    """
    _inherit = 'final.wo.roll.input'

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec._sync_input_roll_stock(rec._get_input_roll_lot())
        return recs

    def write(self, vals):
        res = super().write(vals)
        if 'consumed_qty' in vals or 'previous_roll_id' in vals:
            for rec in self:
                rec._sync_input_roll_stock(rec._get_input_roll_lot())
        return res

    def unlink(self):
        # Give the stock back before the line (and its consumption) is gone.
        self._sync_input_roll_stock()
        return super().unlink()

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
        """Make stock reflect this line's consumed quantity of ``lot``.

        Without ``lot`` everything posted for the line is returned (line
        deleted, input roll removed or changed).

        Like the parent sync this never stops an operator from saving: a
        stock problem is logged and posted on the MO, and the next save
        retries (the quantity to post is always target minus already posted).
        """
        for line in self:
            posted = line._get_posted_input_roll_qty()
            targets = {lot: line.consumed_qty or 0.0} if lot else {}
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
