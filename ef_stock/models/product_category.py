# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductCategory(models.Model):
    _inherit = 'product.category'

    tow_user_id = fields.Many2one(
        'res.users',
        string='TOW Operator',
    )