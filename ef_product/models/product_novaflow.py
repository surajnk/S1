from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
import re

class ExtraKnives(models.Model):
    _name = 'product.novaflow'
    _description = 'Product Novaflow'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    #_rec_name = 'x_extra_knives'

    name = fields.Char('Novaflow')
    x_novaflow_product = fields.Many2one("product.product",string="Product")
    x_product_description = fields.Char('Description')

    _sql_constraints = [
        (
            'unique_novaflow_product',
            'UNIQUE(x_novaflow_product)',
            'A Novaflow record for this product already exists!'
        ),
    ]

    @api.constrains('x_novaflow_product')
    def _check_unique_product(self):
        for rec in self:
            if not rec.x_novaflow_product:
                continue
            duplicate = self.search([
                ('x_novaflow_product', '=', rec.x_novaflow_product.id),
                ('id', '!=', rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f'A Novaflow record already exists for product '
                    f'"{rec.x_novaflow_product.display_name}". '
                    f'Duplicate entry is not allowed.'
                )

    def _sync_name_to_product(self):
        """Push novaflow name onto the linked product.product record."""
        for rec in self:
            if rec.x_novaflow_product:
                rec.x_novaflow_product.sudo().write({
                    'x_product_product_novaflow': rec.id,
                })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_name_to_product()
        return records

    def write(self, vals):
        # Capture old products BEFORE the write, in case product is being swapped
        old_products = {}
        if 'x_novaflow_product' in vals:
            for rec in self:
                old_products[rec.id] = rec.x_novaflow_product

        res = super().write(vals)

        if 'name' in vals or 'x_novaflow_product' in vals:
            # Clear name from old product if product was swapped
            for rec in self:
                old_product = old_products.get(rec.id)
                if old_product and old_product != rec.x_novaflow_product:
                    old_product.sudo().write({
                        'x_product_product_novaflow': False,
                    })
            self._sync_name_to_product()

        return res