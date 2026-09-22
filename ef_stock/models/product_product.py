from odoo import models
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_open_quants(self):
        action = super().action_open_quants()
        action['domain'] = expression.AND([
            action['domain'],
            ['!', ('lot_id.name', '=like', 'MO/%')],
        ])
        return action
