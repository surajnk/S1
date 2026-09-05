# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MrpWorkCenterProductivity(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    roll_id = fields.Many2one('mrp.wo.roll.line', string='Roll Id')
    quantity = fields.Float(string="Roll Qty")
