from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    inter_warehouse_picking_id = fields.Many2one(
        "stock.picking",
        "Inter-Warehouse Picking",
    )

    def _search_picking_for_assignation_domain(self):
        """Compatibility helper for older Odoo versions.

        Odoo 14.0 introduced :meth:`_search_picking_for_assignation_domain` in
        the base ``stock.move`` model.  Some deployments still run on earlier
        revisions where the method does not exist which causes an
        ``AttributeError`` when our override tries to call it.  Re-implement the
        upstream logic so that the behaviour matches the core method when it is
        missing.
        """
        self.ensure_one()
        domain = [
            ("group_id", "=", self.group_id.id),
            ("location_id", "=", self.location_id.id),
            ("location_dest_id", "=", self.location_dest_id.id),
            ("picking_type_id", "=", self.picking_type_id.id),
            ("printed", "=", False),
            ("immediate_transfer", "=", False),
            (
                "state",
                "in",
                [
                    "draft",
                    "confirmed",
                    "waiting",
                    "partially_available",
                    "assigned",
                ],
            ),
        ]
        if self.partner_id and (
            self.location_id.usage == "transit"
            or self.location_dest_id.usage == "transit"
        ):
            domain.append(("partner_id", "=", self.partner_id.id))
        return domain

    def _action_done(self, cancel_backorder=False):
        res = super()._action_done(cancel_backorder)
        moves = self.exists().filtered(
            lambda x: x.state == "done" and x.picking_id.type_inter_warehouse_transfer
        )
        moves._push_apply()
        return res

    def _search_picking_for_assignation(self):
        # We do not want to merge pickings made in a transfer
        # between warehouses
        res = super()._search_picking_for_assignation()
        if res and any(
            self.move_orig_ids.mapped("picking_type_id").mapped(
                "disable_merge_picking_moves"
            )
        ):
            domain = self._search_picking_for_assignation_domain()
            picking = (
                self.env["stock.picking"]
                .search(domain)
                .filtered(
                    lambda x: x.move_lines.inter_warehouse_picking_id
                    == self.inter_warehouse_picking_id
                )
            )
            return picking or False
        return res
