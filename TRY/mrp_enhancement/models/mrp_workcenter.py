# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil import relativedelta
import datetime

from odoo import api, exceptions, fields, models, _


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    location_id = fields.Many2one('stock.location', 'Location', required=True, copy=True)
