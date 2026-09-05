from odoo import api, fields, models

class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    vendor_product_code = fields.Char('Vendor Product Code')
    purchase_product_break_codes_id = fields.Many2one('purchase.product.break.codes', 'Purchase Break Code')
