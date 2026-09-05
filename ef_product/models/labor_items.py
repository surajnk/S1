from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

class LaborItems(models.Model):
    _name = 'labor.items'
    _description = 'Labor Items'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Labor Code')
    x_Description = fields.Char('Description')
    x_qty_break = fields.Many2one('product.break.codes','Quantity Break Code')
    x_min_charge = fields.Float('Minimum Charge')
    x_labor_account = fields.Many2one('account.account','Labor Account')
    x_product_labor_commodity = fields.Many2one('product.commodity.code','Commodity Code')
    x_in_sales = fields.Boolean('Included in Sales')
    x_customer_units = fields.Boolean('Use Customer Units')
    x_m2_extra_knives = fields.Many2one('extra.knives','Extra Knives')
    x_no_of_break_quantities_grid = fields.One2many('labor.items.sub','x_labor_item','Quantity Break Charges')

    @api.constrains('x_min_charge')
    def _check_negativ_values(self):
        for rec in self:
            if rec.x_min_charge < 0.00:
                raise ValidationError("Minimum charge cannot be less than zero.")

    @api.onchange('x_qty_break')
    def fetch_qty(self):
    	val = {}
    	res = []
    	for rec in self:
    		res=[(5,0,0)]
    		if self.x_qty_break:
    			for qc in self.x_qty_break.x_no_of_break_quantities_grid:
    				val = {
    				'name': qc.x_breakqty
    				}
    				res.append((0,0,val))
    			rec.x_no_of_break_quantities_grid = res



class LaborItemsSub(models.Model):
    _name = 'labor.items.sub'
    _description = 'Labor Items Sub'

    name = fields.Char('Quantity', required=True)
    x_charge = fields.Float('Charge',digits='EF Price')
    x_slitting =  fields.Boolean('Slitting')
    x_labor_item = fields.Many2one('labor.items','Break')
