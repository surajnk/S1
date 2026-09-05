# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MrpWorkCenter(models.Model):
    _inherit = 'mrp.workcenter'

    show_partial_produce = fields.Boolean("Show Partial Produce")
