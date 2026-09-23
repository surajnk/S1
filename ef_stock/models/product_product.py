from odoo import models
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_open_quants(self):
        action = super().action_open_quants()
        action['context'] = dict(action.get('context') or {}, search_default_hide_mo_lots=1)
        return action

    def _get_domain_locations(self):
        domain_quant_loc, domain_move_in_loc, domain_move_out_loc = super()._get_domain_locations()
        if self.env.company.exclude_mo_lot_qty:
            domain_quant_loc = expression.AND([
                domain_quant_loc,
                ['!', ('lot_id.name', '=like', 'MO/%')],
            ])
        return domain_quant_loc, domain_move_in_loc, domain_move_out_loc
