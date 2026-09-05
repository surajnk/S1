from itertools import chain
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_repr
from odoo.tools.misc import get_lang


class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    applied_on = fields.Selection([
        ('7_commodity_group', 'Commodity Group'),
        ('6_price_group', 'Price Group'),
        ('5_labor_item', 'Labor Item'),
        ('4_item_group', 'Item Group'),
        ('3_global', 'All Products'),
        ('2_product_category', 'Product Category'),
        ('1_product', 'Product'),
        ('0_product_variant', 'Product Variant')], "Apply On",
        default='3_global', required=True,
        help='Pricelist Item applicable on selected option')
    product_item_group_id = fields.Many2one('product.item.group', 'Item Group')
    labor_item_id = fields.Many2one('labor.items', 'Labor Item')
    product_commodity_id = fields.Many2one('product.commodity.code', 'Product Commodity Code')
    price_group_id = fields.Many2one('price.group','Price Group')

    @api.depends('applied_on', 'categ_id', 'product_tmpl_id', 'product_id', 'compute_price', 'fixed_price', \
        'pricelist_id', 'percent_price', 'price_discount', 'price_surcharge')
    def _get_pricelist_item_name_price(self):
        for item in self:
            if item.categ_id and item.applied_on == '2_product_category':
                item.name = _("Category: %s") % (item.categ_id.display_name)
            elif item.product_tmpl_id and item.applied_on == '1_product':
                item.name = _("Product: %s") % (item.product_tmpl_id.display_name)
            elif item.product_id and item.applied_on == '0_product_variant':
                item.name = _("Variant: %s") % (item.product_id.with_context(display_default_code=False).display_name)
            elif item.applied_on == '4_item_group':
                item.name = _("Item Group: %s") % (item.product_item_group_id.name)
            elif item.applied_on == '5_labor_item':
                item.name = _("Labor Item : %s") % (item.labor_item_id.name)
            elif item.applied_on == '6_price_group':
                item.name = _("Price Group: %s") % (item.price_group_id.x_pricegroup)
            elif item.applied_on == '7_commodity_group':
                item.name = _("Product Commodity: %s") % (item.product_commodity_id.name)
            else:
                item.name = _("All Products")

            if item.compute_price == 'fixed':
                decimal_places = self.env['decimal.precision'].precision_get('Product Price')
                if item.currency_id.position == 'after':
                    item.price = "%s %s" % (
                        float_repr(
                            item.fixed_price,
                            decimal_places,
                        ),
                        item.currency_id.symbol,
                    )
                else:
                    item.price = "%s %s" % (
                        item.currency_id.symbol,
                        float_repr(
                            item.fixed_price,
                            decimal_places,
                        ),
                    )
            elif item.compute_price == 'percentage':
                item.price = _("%s %% discount", item.percent_price)
            else:
                item.price = _("%(percentage)s %% discount and %(price)s surcharge", percentage=item.price_discount, price=item.price_surcharge)

    @api.onchange('applied_on')
    def _onchange_applied_on(self):
        res1=[]
        for item in self:
            if item.applied_on == '2_product_category':
                res1=[(5,0,0)]
                item.x_pricelist_break_qty_price = res1
            elif item.product_tmpl_id and item.applied_on == '1_product':
                res1=[(5,0,0)]
                item.x_pricelist_break_qty_price = res1
            elif item.product_id and item.applied_on == '0_product_variant':
                res1=[(5,0,0)]
                item.x_pricelist_break_qty_price = res1
            elif item.applied_on == '4_item_group':
                res1=[(5,0,0)]
                item.x_pricelist_break_qty_price = res1
            elif item.applied_on == '5_labor_item':
                res1=[(5,0,0)]
                item.x_pricelist_break_qty_price = res1
            elif item.applied_on == '7_commodity_group':
                res1=[(5,0,0)]
                item.x_pricelist_break_qty_price = res1
            elif item.applied_on == '6_price_group':
                res1=[(5,0,0)]
                item.x_pricelist_break_qty_price = res1
            else:
                res1=[(5,0,0)]
                item.x_pricelist_break_qty_price = res1

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('applied_on', False):
                # Ensure item consistency for later searches.
                applied_on = values['applied_on']
                if applied_on == '3_global':
                    values.update(dict(product_id=None, product_tmpl_id=None, categ_id=None))
                elif applied_on == '2_product_category':
                    values.update(dict(product_id=None, product_tmpl_id=None))
                elif applied_on == '1_product':
                    values.update(dict(product_id=None, categ_id=None))
                elif applied_on == '0_product_variant':
                    values.update(dict(categ_id=None))
        return super(PricelistItem, self).create(vals_list)
