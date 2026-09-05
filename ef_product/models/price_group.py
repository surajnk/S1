from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

class PriceGroup(models.Model):
    _name = 'price.group'
    _description = 'Price Group'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'x_pricegroup'

    x_pricegroup = fields.Char('Price Group')
    x_description = fields.Char('Description')
    x_effectivedate = fields.Date('Effective Date')
    x_qty_break_code = fields.Many2one('product.break.codes','Quantity Break Code')
    x_futuredate = fields.Date('Date future moved to current')
    x_price_group_qty = fields.Char('No of Break Quantities')
    x_sale_price = fields.One2many('price.group.sub','x_price_parent','Selling Price')

    @api.onchange('x_qty_break_code')
    def fetch_breakpts(self):
        for rec in self:
            if rec.x_qty_break_code:
                self.x_price_group_qty = rec.x_qty_break_code.no_of_breaks
                val2={}
                rec.write({'x_sale_price': [(5, 0, val2)]})
                res=[(5,0,0)]
                for qc in rec.x_qty_break_code.x_no_of_break_quantities_grid:
                    val = {
                    'x_price_qty': qc.x_breakqty
                    }
                    res.append((0,0,val))
                rec.x_sale_price = res

    @api.model
    def price_increase(self):
        today = datetime.date.today()

        price_groups = env['price.group'].search([
            ('x_futuredate', '<=', today),
            ('x_futuredate', '!=', False),
        ])

        for group in price_groups:

            for group_line in group.x_sale_price:
                if group_line.x_future_selling_price:
                    group_line.write({
                        'x_selling_price': group_line.x_future_selling_price
                    })

            products = env['product.template'].search([
                ('x_product_price_group', '=', group.id)
            ])

            for product in products:

                for group_line in group.x_sale_price:
                    product_lines = product.x_break_qty_price.filtered(
                        lambda l: l.x_product_qty == group_line.x_price_qty
                    )

                    for product_line in product_lines:
                        product_line.write({
                            'x_product_price_per_value': group_line.x_selling_price
                        })

            group.write({
                'x_futuredate': False
            })



    # @api.constrains('x_price_group_qty', 'x_sale_price')
    # def _check_break_quantities(self):
    #     for rec in self:
    #         omlen = len(rec.x_sale_price)
    #         if omlen > int(rec.x_price_group_qty):
    #             raise ValidationError("Number of Price Groups is more than Number of Break Quantities.")


class PriceGroupSub(models.Model):
    _name = 'price.group.sub'
    _description = 'Price Group Sub'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    x_price_qty = fields.Char('Quantities')
    x_selling_price = fields.Float('Selling Price',digits='EF Price')
    x_future_selling_price = fields.Float('Future Selling Price',digits='EF Price')
    x_price_parent = fields.Many2one('price.group','Selling Price')


class ProductTolerance(models.Model):
    _name = 'product.tolerance'
    _rec_name = 'x_tolerance_level'
    _description = 'Product Tolerance'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    x_tolerance_level = fields.Char('Level')
    x_tolerance_description = fields.Char('Description')
    x_tolerance_lines = fields.One2many('product.tolerance.sub','x_tolerance_parent','Tolerance Range')

class ProductToleranceSub(models.Model):
    _name = 'product.tolerance.sub'
    _description = 'Product Tolerance Lines'
    _inherit = ['mail.thread', 'mail.activity.mixin']    

    x_range_tolerance_yds = fields.Char('Range(yds)')
    x_tolerance_over = fields.Integer('Over %')
    x_tolerance_under = fields.Integer('Under %')
    x_tolerance_parent = fields.Many2one('product.tolerance','Tolerance')