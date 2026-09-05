# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    planned_variances_account_id = fields.Many2one('account.account', "Planned Variance Cost Account")
    material_variances_account_id = fields.Many2one('account.account', "Components Variance Cost Account")
    other_variances_account_id = fields.Many2one('account.account', "Other Variance Cost Account")
    manufacturing_journal_id = fields.Many2one('account.journal', "Manufacturing journal id")
    labour_cost_account_id = fields.Many2one('account.account', "Labour Variable Cost Account")
    machine_run_cost_account_id = fields.Many2one('account.account', "Machine Run Variable Cost Account")
    labour_fixed_cost_account_id = fields.Many2one('account.account', "Labour Fixed Cost Account")
    machine_run_fixed_cost_account_id = fields.Many2one('account.account', "Machine Run Fixed Cost Account")


class MrpProdCostParameters (models.TransientModel):
    _name = 'mrp.product.costing.parameters'
    _description = 'mrp product costing setting'
    _rec_name = "company_id"

    planned_variances_account_id = fields.Many2one('account.account', "Planned Variance Cost Account*", related="company_id.planned_variances_account_id", readonly=False)
    material_variances_account_id = fields.Many2one('account.account', "Material Variances Cost Account*", related="company_id.material_variances_account_id", readonly=False)
    other_variances_account_id = fields.Many2one('account.account', "Other Variances Cost Account*", related="company_id.other_variances_account_id", readonly=False)
    manufacturing_journal_id = fields.Many2one('account.journal', "Manufacturing journal id*", related="company_id.manufacturing_journal_id", readonly=False)
    company_id = fields.Many2one('res.company', 'Company', required=True, default=lambda self: self.env.user.company_id)
    labour_cost_account_id = fields.Many2one('account.account', "Labour Variable Cost Account*", related="company_id.labour_cost_account_id", readonly=False)
    machine_run_cost_account_id = fields.Many2one('account.account', "Machine Run Variable Cost Account*", related="company_id.machine_run_cost_account_id", readonly=False)
    labour_fixed_cost_account_id = fields.Many2one('account.account', "Labour Fixed Cost Account*", related="company_id.labour_fixed_cost_account_id", readonly=False)
    machine_run_fixed_cost_account_id = fields.Many2one('account.account', "Machine Run Fixed Cost Account*", related="company_id.machine_run_fixed_cost_account_id", readonly=False)
