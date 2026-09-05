from odoo import api, fields, models, tools, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    count_purchase_orders = fields.Integer('Purchase Order', compute='_count_purchase_order')

    def _count_purchase_order(self):
        for so in self:
            so.count_purchase_orders = self.env['purchase.order'].search_count([('sale_order_id', '=', so.id)])
