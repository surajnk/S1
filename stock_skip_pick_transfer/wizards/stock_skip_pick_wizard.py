from odoo import fields, models
from odoo.tools import float_compare


class StockSkipPickWizard(models.TransientModel):
    _name = "stock.skip.pick.wizard"
    _description = "Skip Pick Transfer Confirmation"

    source_picking_id = fields.Many2one(
        "stock.picking", string="Source Transfer", required=True, readonly=True
    )
    line_ids = fields.One2many(
        "stock.skip.pick.wizard.line", "wizard_id", string="Pending Pick Transfers"
    )

    def action_confirm(self):
        self.ensure_one()
        source_picking = self.source_picking_id
        rounding = self.env["decimal.precision"].precision_get("Product Unit of Measure")
        for line in self.line_ids.filtered("skip"):
            if float_compare(line.quantity, 0.0, precision_digits=rounding) <= 0:
                continue
            source_picking._skip_pick_move(line.pick_move_id, line.quantity, source_picking)
        return source_picking.with_context(skip_pick_wizard_done=True).button_validate()

    def action_keep_normal_flow(self):
        self.ensure_one()
        return self.source_picking_id.with_context(
            skip_pick_wizard_done=True
        ).button_validate()


class StockSkipPickWizardLine(models.TransientModel):
    _name = "stock.skip.pick.wizard.line"
    _description = "Skip Pick Transfer Line"

    wizard_id = fields.Many2one(
        "stock.skip.pick.wizard", required=True, ondelete="cascade"
    )
    pick_move_id = fields.Many2one("stock.move", string="Pick Move", required=True, readonly=True)
    pick_picking_id = fields.Many2one("stock.picking", string="Pick Transfer", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    quantity = fields.Float(string="Quantity to Ship Now")
    skip = fields.Boolean(string="Skip Pick", default=True)
