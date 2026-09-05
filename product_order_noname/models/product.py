from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"
    _order = "default_code, id"

    @api.model
    @api.depends('name')
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('default_code', operator, name)]

        products = self.search(domain + args, limit=limit)
        return [(p.id, f"{p.name or ''} - {p.default_code or ''}") for p in products]

