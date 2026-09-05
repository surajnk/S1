# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


#class PurchaseOrder(models.Model):
#    _inherit = 'purchase.order'

    #origin = fields.Char(readonly=True)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # purchase_stock module
    # create purchase order item with analytic account
    def _prepare_purchase_order_line_from_procurement(self, product_id, product_qty, product_uom, company_id, values, po):
        res = super()._prepare_purchase_order_line_from_procurement(product_id, product_qty, product_uom, company_id, values, po)
        res.update({'account_analytic_id': values.get('account_analytic_id', False)})
        return res

