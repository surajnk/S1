from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

class ProductItemGroup(models.Model):
    _name = 'product.item.group'
    _description = 'Product Item Group'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Group Code')
    x_Description = fields.Char('Description')
    x_commodity_class = fields.Many2one('product.commodity.code',string='Commodity Class')
    x_basis_size = fields.Integer('Basis Size')
    x_basis_weight = fields.Integer('Basis Weight')
    x_caliper = fields.Float('Caliper',digits='EF Product')

    @api.constrains('x_caliper','x_basis_size','x_basis_weight')
    def _check_neg_values(self):
        for rec in self:
            if rec.x_caliper < 0.00:
                raise ValidationError("Caliper value cannot be less than zero.")
            if rec.x_basis_size < 0:
            	raise ValidationError("Basis Size value cannot be less than zero.")
            if rec.x_basis_weight < 0:
            	raise ValidationError("Basis Weight value cannot be less than zero.")