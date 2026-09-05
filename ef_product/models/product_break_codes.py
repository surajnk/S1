from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

class ProductBreakCodes(models.Model):
    _name = 'product.break.codes'
    _description = 'Product Break Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Break Code')
    no_of_breaks = fields.Integer('Number of Breaks')
    x_no_of_break_quantities_grid = fields.One2many('product.break.quantities','x_break_quantities','Break Quantity')

    @api.constrains('no_of_breaks', 'x_no_of_break_quantities_grid')
    def _check_break_code_quantities(self):
        for rec in self:
            omlength = len(rec.x_no_of_break_quantities_grid)
            if omlength > int(rec.no_of_breaks):
                raise ValidationError("Number of Break Quantities is more than Number of breaks defined.")


class ProductBreakQuantities(models.Model):
    _name = 'product.break.quantities'
    _description = 'Product Break Quantities'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    x_breakqty = fields.Char('Break Quantity')
    x_break_quantities = fields.Many2one('product.break.codes','Break')