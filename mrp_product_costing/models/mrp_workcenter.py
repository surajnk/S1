# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'


    WORKCENTER_TYPE = [
        ('H', 'Man'),
        ('M', 'Machine'),
    ]

    wc_type = fields.Selection(WORKCENTER_TYPE, 'Work Center Type')
    costs_hour = fields.Float('Hourly Direct Cost Rate', default="0.0")
    costs_hour_fixed = fields.Float('Hourly Fixed Direct Cost Rate', default="0.0")
    costs_overhead_variable_percentage = fields.Float('Variable OVH Costs percentage', default="0.0")
    costs_overhead_fixed_percentage = fields.Float('Fixed OVH Costs percentage', default="0.0")
    analytic_account_id = fields.Many2one('account.analytic.account', "Analytic Account")
    costing_account_id = fields.Many2one('account.account', "Labour Cost Account")
    ovh_costing_account_id = fields.Many2one('account.account', "Overhead Cost Account")
    labor_costs_hour = fields.Float('Labor Cost')
    overhead_costs_hour = fields.Float('Overhead Cost')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id.id)



