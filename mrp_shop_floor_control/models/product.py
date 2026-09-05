# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class Product(models.Model):

    _inherit = 'product.product'

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if self._context.get('only_mrp_components'):
                production_rec = self.env['mrp.production'].browse(self._context.get('only_mrp_components'))
                args = [('id', 'in', [sm_rec.product_id.id for sm_rec in production_rec.move_raw_ids if sm_rec.product_id])]
        return super(Product, self)._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)
