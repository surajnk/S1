from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

class PurchaseProductBreakCodes(models.Model):
    _name = 'purchase.product.break.codes'
    _description = 'Purchase Product Break Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Break Code')
    effective_date = fields.Date('Effective Date')
    no_of_breaks = fields.Integer('Number of Breaks')
    purchase_product_break_codes_line = fields.One2many('purchase.product.break.codes.line', 'purchase_product_break_codes_id', 'Break Quantity')

    @api.constrains('no_of_breaks', 'purchase_product_break_codes_line')
    def _check_break_code_quantities(self):
        for rec in self:
            if len(rec.purchase_product_break_codes_line) > rec.no_of_breaks:
                raise ValidationError("Number of Break Quantities is more than Number of breaks defined.")


class PurchaseProductBreakCodesLine(models.Model):
    _name = 'purchase.product.break.codes.line'
    _description = 'Purchase Product Break Code Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    break_qty = fields.Char('Break Quantity')
    selling_price = fields.Float('Cost Price',digits='EF Price')
    future_selling_price = fields.Float('Future Cost Price',digits='EF Price')
    purchase_product_break_codes_id = fields.Many2one('purchase.product.break.codes','Break')
