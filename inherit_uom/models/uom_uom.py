from odoo import models, fields

class UoM(models.Model):
    _inherit = 'uom.uom'

    x_frequent = fields.Boolean(string="Sales UoM")
    x_frequent_purchase = fields.Boolean(string="Purchase UoM")
    