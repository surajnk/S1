from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    prompt_skip_pick = fields.Boolean(
        string="Offer to Skip Pick on Validate",
        help=(
            "When validating a transfer of this operation type, if its "
            "product(s) can satisfy a pending Pick transfer in the same "
            "warehouse, offer the user the choice to skip that Pick "
            "transfer and send the stock straight through to Pack/Delivery."
        ),
    )
