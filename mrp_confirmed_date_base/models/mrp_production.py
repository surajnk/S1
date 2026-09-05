# -*- coding: utf-8 -*-

from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    x_mrp_confirmed_date = fields.Date(
        string='Confirmed Date',
        help='Confirmed manufacturing date used for planning calculations',
    )

