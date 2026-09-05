from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

class ProductEmbossing(models.Model):
    _name = 'product.embossing'
    _description = 'Product Embossings'
    _rec_name = 'name'

    name = fields.Char('Name')
    x_pattern_embossing_number = fields.Integer('Pattern #')
    x_embossing_code = fields.Char('Code')
    x_embossing_frame = fields.Many2one('mrp.workcenter','Work-Center')
    x_embossing_branch_id = fields.Many2one('res.branch', string='Branch')
    x_max_width = fields.Float('Max Width Allowed')
    x_no_of_cylinders = fields.Integer('No. Of Cylinders')
    state = fields.Selection([
        ('Active', 'Active'),
        ('Out Of Service', 'Out Of Service'),
        ('Discontinued', 'Discontinued'),
        ], string='Status',)
