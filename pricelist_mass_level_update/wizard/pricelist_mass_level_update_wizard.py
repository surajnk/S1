from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


class PricelistMassLevelUpdateWizard(models.TransientModel):
    _name = 'pricelist.mass.level.update.wizard'
    _description = 'Mass update Level Price on quantity breaks'

    # Scope / filters
    pricelist_ids = fields.Many2many('product.pricelist', string='Restrict to Pricelists')

    scope = fields.Selection([
        ('7_commodity_group', 'Commodity Group'),
        ('6_price_group', 'Price Group'),
        ('5_labor_item', 'Labor Item'),
        ('4_item_group', 'Item Group'),
        ('3_global', 'All Products'),
        ('2_product_category', 'Product Category'),
        ('1_product', 'Product'),
        ('0_product_variant', 'Product Variant')
    ], string='Apply On', required=True, default='1_product')

    # Target fields (one of these is used depending on `scope`)
    product_tmpl_id = fields.Many2one('product.template', string='Product')
    product_id = fields.Many2one('product.product', string='Product Variant')
    categ_id = fields.Many2one('product.category', string='Product Category')
    product_item_group_id = fields.Many2one('product.item.group', string='Item Group')
    labor_item_id = fields.Many2one('labor.items', string='Labor Item')
    price_group_id = fields.Many2one('price.group', string='Price Group')
    product_commodity_id = fields.Many2one('product.commodity.code', string='Commodity Group')

    # Change spec
    percentage = fields.Float(string='Percentage (%)', required=True,
                              help='e.g., 10 increases by +10%%, -5 decreases by 5%%.')
    round_to_precision = fields.Boolean(string='Round to EF Price precision', default=True)

    def _required_for_scope(self):
        """Return the field name required for the selected scope (if any)."""
        self.ensure_one()
        mapping = {
            '1_product': 'product_tmpl_id',
            '0_product_variant': 'product_id',
            '2_product_category': 'categ_id',
            '4_item_group': 'product_item_group_id',
            '5_labor_item': 'labor_item_id',
            '6_price_group': 'price_group_id',
            '7_commodity_group': 'product_commodity_id',
            '3_global': None,
        }
        return mapping.get(self.scope)

    @api.onchange('scope')
    def _onchange_scope(self):
        # Clear non-relevant fields when scope changes
        for w in self:
            for fname in ['product_tmpl_id','product_id','categ_id','product_item_group_id',
                          'labor_item_id','price_group_id','product_commodity_id']:
                if fname != (w._required_for_scope() or ''):
                    w[fname] = False

    def action_apply(self):
        self.ensure_one()
        # Validate target
        req = self._required_for_scope()
        target_id = False
        if req:
            target = self[req]
            if not target:
                raise UserError(_("Please set: %s") % (self._fields[req].string))
            target_id = target.id

        # Build domain for product.pricelist.item
        domain = [('applied_on', '=', self.scope)]
        if self.pricelist_ids:
            domain.append(('pricelist_id', 'in', self.pricelist_ids.ids))
        if req and target_id:
            domain.append((req, '=', target_id))

        Item = self.env['product.pricelist.item']
        items = Item.search(domain)

        if not items:
            raise UserError(_("No pricelist items found for the selected filters."))

        # dp for rounding
        dp_model = self.env['decimal.precision']
        ef_prec = dp_model.precision_get('EF Price') if self.round_to_precision else 6

        factor = 1.0 + (self.percentage or 0.0) / 100.0
        if factor <= 0:
            raise UserError(_("Resulting factor must be > 0."))

        line_model = self.env['product.quantity.pricelist']
        total_lines = 0
        for it in items:
            # only standard quantity-break table
            for line in it.x_pricelist_break_qty_price:
                old = line.x_product_price_per_value_pr or 0.0
                # if it's zero everywhere and you still want to update zeros, remove the `or 0.0`
                new = old * factor
                new_val = float(f"{new:.{ef_prec}f}") if self.round_to_precision else new

                # precision-aware comparison to avoid false equals
                if float_compare(new_val, old, precision_digits=ef_prec) != 0:
                    line.write({'x_product_price_per_value_pr': new_val})
                    total_lines += 1

        # User feedback
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Pricelist Level Prices updated'),
                'message': _('%s line(s) updated across %s item(s).') % (total_lines, len(items)),
                'sticky': False,
            }
        }
