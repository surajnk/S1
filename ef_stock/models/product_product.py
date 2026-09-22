from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_open_quants(self):
        action = super().action_open_quants()
        action['context'] = dict(action.get('context') or {}, search_default_hide_mo_lots=1)
        return action
