# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    finite_capacity_scheduling = fields.Boolean(
        string='Enable Finite Capacity Scheduling',
        config_parameter='mrp_finite_capacity_control.finite_capacity_scheduling',
        help='When enabled, workorder scheduling respects workcenter capacity '
             'and prevents overlapping or past schedules.'
    )
