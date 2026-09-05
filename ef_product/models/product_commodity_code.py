from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

class ProductCommodityCode(models.Model):
    _name = 'product.commodity.code'
    _description = 'Product Commodity Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Commodity Class')
    x_Description = fields.Char('Description')
    x_trim_width = fields.Float('Trim Width')
    x_trim_length = fields.Float('Trim Length')
    x_waste = fields.Float('Waste(%)')
    x_min_antique_order = fields.Integer('Min. Antique Order')
    x_min_amboss_order = fields.Integer('Min. Emboss Order')
    x_allow_ambossing = fields.Boolean('Allow Embossing')
    x_sheet_orientation = fields.Selection([
        ('sheetfaceup', 'Sheets Face Up'),
        ('sheetfacedown', 'Sheets Face Down')], 'Sheet Orientation')
    x_roll_orientation = fields.Selection([
        ('windfaceout', 'Wind Face Out'),
        ('windfacein', 'Wind Face In')], 'Roll Orientation')
    x_HS_Code = fields.Many2one('product.harmonized.codes','HS Code')
    x_labor_items_grid = fields.One2many('product.commodity.code.labor','x_labor_commodity','Labor Items')

    @api.constrains('x_trim_width','x_trim_length','x_waste','x_min_antique_order','x_min_amboss_order')
    def _check_negative_values(self):
        for rec in self:
            if rec.x_trim_width < 0.00:
                raise ValidationError("Trim Width value cannot be less than zero.")
            if rec.x_trim_length < 0.00:
                raise ValidationError("Trim Length value cannot be less than zero.")
            if rec.x_waste < 0.00:
                raise ValidationError("Waste(%) value cannot be less than zero.")
            if rec.x_min_antique_order < 0:
                raise ValidationError("Min. Antique Order value cannot be less than zero.")
            if rec.x_min_amboss_order < 0:
                raise ValidationError("Min. Amboss Order value cannot be less than zero.")

class ProductCommodityCodeLabor(models.Model):
    _name = 'product.commodity.code.labor'
    _description = 'Product Commodity Code Labor'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    x_labor_item = fields.Many2one('labor.items','Labor Items')
    x_labor_commodity = fields.Many2one('product.commodity.code','Commodity Labor')