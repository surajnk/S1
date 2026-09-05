from odoo import api, fields, models

class ProductHarmonizedCodes(models.Model):
    _name = 'product.harmonized.codes'
    _description = 'Product Harmonized Codes'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('HS Code')
    x_keycode = fields.Char('Key Code')
    x_Description = fields.Char('Description')
    x_Generic_Desc = fields.Char('Generic Desc')