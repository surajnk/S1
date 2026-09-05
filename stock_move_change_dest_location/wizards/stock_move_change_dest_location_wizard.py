from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockMoveChangeDestLocation(models.TransientModel):
    _name = "stock.move.change.dest.location.wizard"
    _description = "Stock Move Change Destination Location Wizard"

    def _prepare_default_values(self, picking):
        warehouse = picking.location_dest_id.get_warehouse()
        return {"warehouse_view_location_id": warehouse.view_location_id.id if warehouse else False}

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        active_model = self.env.context["active_model"]
        active_ids = self.env.context["active_ids"] or []
        picking = self.env[active_model].browse(active_ids)
        res.update(self._prepare_default_values(picking))
        return res

    def _default_old_location_id(self):
        stock_picking_obj = self.env["stock.picking"]
        pickings = stock_picking_obj.browse(self.env.context["active_ids"])
        first_move = pickings.mapped("move_lines")[:1]
        return first_move.location_dest_id.id

    def _get_allowed_old_location_domain(self):
        stock_picking_obj = self.env["stock.picking"]
        pickings = stock_picking_obj.browse(self.env.context.get("active_ids", []))
        return [("id", "in", pickings.mapped("move_lines.location_dest_id").ids)]

    def _get_allowed_new_location_domain(self):
        return [("usage", "=", "internal")]

    def _get_allowed_states(self):
        return ["waiting", "partially_available", "confirmed", "assigned"]

    warehouse_view_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Warehouse View Location",
        readonly=True,
    )
    old_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="Old destination",
        default=_default_old_location_id,
        domain=lambda self: self._get_allowed_old_location_domain(),
    )
    new_location_id = fields.Many2one(
        comodel_name="stock.location",
        string="New destination",
        required=True,
        domain=_get_allowed_new_location_domain,
    )
    moves_to_change = fields.Selection(
        selection=[
            ("all", "Change All moves"),
            ("matched", "Change only moves with matched OLD location"),
            ("manual", "Select move lines to change"),
        ],
        string="Operations to change",
        required=True,
        default="all",
        help="Select which kind of selection of the moves you want to do",
    )
    # Many2many on stock.move.line so each lot appears as a separate row
    move_line_ids = fields.Many2many(
        "stock.move.line",
        string="Move lines",
    )

    def _check_allowed_pickings(self, pickings):
        forbidden_pickings = pickings.filtered(
            lambda x: x.state not in self._get_allowed_states()
        )
        if forbidden_pickings:
            raise UserError(
                _(
                    "You can not change move destination location if "
                    "picking state is not in %s"
                )
                % ", ".join(self._get_allowed_states())
            )

    def _check_allowed_moves(self, moves):
        forbidden_moves = moves.filtered(
            lambda x: x.state not in self._get_allowed_states()
        )
        if forbidden_moves:
            raise UserError(
                _(
                    "You can not change move destination location if "
                    "the move state is not in %s"
                )
                % ", ".join(self._get_allowed_states())
            )

    def action_apply(self):
        stock_picking_obj = self.env["stock.picking"]
        pickings = stock_picking_obj.browse(self.env.context["active_ids"])
        self._check_allowed_pickings(pickings)
        all_moves = pickings.mapped("move_lines")

        new_loc = self.new_location_id.id

        if self.moves_to_change == "all":
            moves_to_change = all_moves
            self._check_allowed_moves(moves_to_change)
            # Update move level
            moves_to_change.write({"location_dest_id": new_loc})
            # Update all move lines
            detail_lines = moves_to_change.mapped("move_line_ids").filtered(
                lambda ml: ml.state not in ("done", "cancel")
            )
            detail_lines.write({"location_dest_id": new_loc})

        elif self.moves_to_change == "matched":
            moves_to_change = all_moves.filtered(
                lambda x: x.location_dest_id == self.old_location_id
            )
            self._check_allowed_moves(moves_to_change)
            moves_to_change.write({"location_dest_id": new_loc})
            detail_lines = moves_to_change.mapped("move_line_ids").filtered(
                lambda ml: ml.state not in ("done", "cancel")
            )
            detail_lines.write({"location_dest_id": new_loc})

        else:
            # Manual: user selected individual stock.move.line records
            # Each lot is a separate row so selection is per-lot
            selected_lines = self.move_line_ids.filtered(
                lambda ml: ml.state not in ("done", "cancel")
            )
            self._check_allowed_moves(selected_lines.mapped("move_id"))
            # Write destination on the selected move lines
            selected_lines.write({"location_dest_id": new_loc})
            # Only update the parent stock.move if ALL its active lines
            # were selected — avoids inconsistency when only some lots change
            affected_moves = selected_lines.mapped("move_id")
            for move in affected_moves:
                active_lines = move.move_line_ids.filtered(
                    lambda ml: ml.state not in ("done", "cancel")
                )
                if all(ml in selected_lines for ml in active_lines):
                    move.write({"location_dest_id": new_loc})

        return {"type": "ir.actions.act_window_close"}
