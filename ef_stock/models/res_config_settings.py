from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    exclude_mo_lot_qty = fields.Boolean(
        'Exclude MO Lots from Available Quantity',
        help="When enabled, quantities held in lots whose number starts with "
             "\"MO/\" are not counted in a product's On Hand / Available Quantity.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    exclude_mo_lot_qty = fields.Boolean(
        related='company_id.exclude_mo_lot_qty',
        string='Exclude MO Lots from Available Quantity',
        readonly=False,
    )
