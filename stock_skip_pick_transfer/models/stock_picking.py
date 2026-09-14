from odoo import _, models
from odoo.tools import float_compare, float_is_zero


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_skip_pick_candidate_lines(self):
        """Find pending Pick moves that this picking's processed quantities
        could satisfy.

        Returns a list of dicts: {'pick_move': stock.move, 'available_qty': float}
        one entry per (candidate pick move, quantity we could allocate to it),
        never allocating more of a product than this picking actually
        processed for it.
        """
        self.ensure_one()
        candidates = []
        if not self.picking_type_id.prompt_skip_pick:
            return candidates

        warehouse = self.picking_type_id.warehouse_id
        pick_type = warehouse.pick_type_id
        if not pick_type:
            return candidates

        rounding = self.env["decimal.precision"].precision_get("Product Unit of Measure")

        # Quantity actually processed on this picking, per product.
        qty_by_product = {}
        for move in self.move_lines.filtered(lambda m: m.state != "cancel"):
            qty_done = sum(move.move_line_ids.mapped("qty_done"))
            if float_is_zero(qty_done, precision_digits=rounding):
                continue
            qty_by_product[move.product_id] = qty_by_product.get(move.product_id, 0.0) + qty_done

        if not qty_by_product:
            return candidates

        # 1) Moves already chained to this picking (e.g. an MTO procurement
        #    linking this transfer's output straight to a Pick move) take
        #    priority — that link is an explicit reservation intent.
        chained_moves = self.move_lines.move_dest_ids.filtered(
            lambda m: m.picking_type_id == pick_type and m.state not in ("done", "cancel")
        )

        # 2) Fall back to any other pending Pick move for the same
        #    product(s) in this warehouse, oldest scheduled date first.
        product_ids = [p.id for p in qty_by_product]
        fallback_moves = self.env["stock.move"].search(
            [
                ("picking_type_id", "=", pick_type.id),
                ("product_id", "in", product_ids),
                ("state", "not in", ("done", "cancel")),
            ],
            order="date asc",
        )

        seen_moves = self.env["stock.move"]
        for move in chained_moves | fallback_moves:
            if move in seen_moves:
                continue
            seen_moves |= move

            available = qty_by_product.get(move.product_id, 0.0)
            if float_is_zero(available, precision_digits=rounding):
                continue

            already_done = sum(move.move_line_ids.mapped("qty_done"))
            remaining_demand = move.product_uom_qty - already_done
            if float_compare(remaining_demand, 0.0, precision_digits=rounding) <= 0:
                continue

            alloc_qty = min(remaining_demand, available)
            qty_by_product[move.product_id] = available - alloc_qty
            candidates.append({"pick_move": move, "available_qty": alloc_qty})

        return candidates

    def button_validate(self):
        if not self.env.context.get("skip_pick_wizard_done"):
            for picking in self:
                candidates = picking._get_skip_pick_candidate_lines()
                if candidates:
                    return picking._open_skip_pick_wizard(candidates)
        return super(
            StockPicking, self.with_context(skip_pick_wizard_done=True)
        ).button_validate()

    def _open_skip_pick_wizard(self, candidates):
        self.ensure_one()
        line_vals = []
        for cand in candidates:
            move = cand["pick_move"]
            line_vals.append(
                (
                    0,
                    0,
                    {
                        "pick_move_id": move.id,
                        "pick_picking_id": move.picking_id.id,
                        "product_id": move.product_id.id,
                        "quantity": cand["available_qty"],
                        "skip": True,
                    },
                )
            )
        wizard = self.env["stock.skip.pick.wizard"].create(
            {"source_picking_id": self.id, "line_ids": line_vals}
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Skip Pick Transfer?"),
            "res_model": "stock.skip.pick.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }

    def _skip_pick_move(self, pick_move, qty, source_picking):
        """Force-complete up to `qty` of `pick_move` (never more than its own
        demand), tracing lots from `source_picking` when the product is
        tracked, then validate the Pick picking — any unmet demand is left
        as a normal backorder, exactly as a manual partial validation would.
        """
        pick_picking = pick_move.picking_id
        pick_picking.action_confirm()

        if pick_move.product_id.tracking != "none":
            self._reserve_from_source_lots(pick_move, qty, source_picking)
        else:
            pick_move._action_assign()

        rounding = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        for move_line in pick_move.move_line_ids:
            if not float_is_zero(move_line.qty_done, precision_digits=rounding):
                continue
            move_line.qty_done = move_line.product_uom_qty

        pick_picking._action_done()

    def _reserve_from_source_lots(self, pick_move, qty, source_picking):
        """Reserve `pick_move` against the same lot(s) that `source_picking`
        just processed for that product, instead of letting the default
        removal strategy pick whichever lot is available in the warehouse.
        """
        rounding = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        source_lines = (
            source_picking.move_lines.filtered(lambda m: m.product_id == pick_move.product_id)
            .mapped("move_line_ids")
            .filtered(lambda ml: not float_is_zero(ml.qty_done, precision_digits=rounding) and ml.lot_id)
        )

        remaining = qty
        for source_line in source_lines:
            if float_compare(remaining, 0.0, precision_digits=rounding) <= 0:
                break

            lot = source_line.lot_id
            quants = self.env["stock.quant"]._gather(
                pick_move.product_id, pick_move.location_id, lot_id=lot, strict=False
            )
            available_in_lot = sum(quants.mapped("quantity")) - sum(
                quants.mapped("reserved_quantity")
            )
            take_qty = min(remaining, source_line.qty_done, available_in_lot)
            if float_compare(take_qty, 0.0, precision_digits=rounding) <= 0:
                continue

            pick_move._update_reserved_quantity(
                take_qty, take_qty, pick_move.location_id, lot_id=lot, strict=False
            )
            remaining -= take_qty
