# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    ovh_var_direct_cost = fields.Float('OVH Variable Direct Cost', digits='Product Price', readonly=True)
    ovh_fixed_direct_cost = fields.Float('OVH Fixed Direct Cost', digits='Product Price', readonly=True)
    ovh_product_cost = fields.Float('OVH Finished Product Cost', digits='Product Price', readonly=True)
    ovh_components_cost = fields.Float('OVH Components Cost', digits='Product Price', readonly=True)
    industrial_cost = fields.Float('Actual Full Industrial Cost', digits='Product Price', readonly=True)
    industrial_cost_unit = fields.Float(' Actual Full Industrial Unit Cost', digits='Product Price', group_operator="avg", readonly=True)
    closure_state = fields.Boolean('Financial Closure Performed', copy=False, default=False)

    def button_closure(self):
        for record in self:
            record.action_variances_postings()
            record.action_economical_closure()
            record.closure_state = 'True'
        return True

    def button_acc_ent(self):
        for rec in self:
            rec.action_ind_material_postings()
        return True


    def action_economical_closure(self):
        for record in self:
            record._wc_ovh_analytic_postings()
            record._bom_ovh_analytic_postings()
            qty_produced = record._get_qty_produced()
            record.industrial_cost = record.direct_cost + record.ovh_var_direct_cost + record.ovh_fixed_direct_cost + record.ovh_product_cost + record.ovh_components_cost
            record.industrial_cost_unit = record.industrial_cost / qty_produced
        return True

    def _wc_ovh_analytic_postings(self):
        fixedamount = 0.0
        varamount = 0.0
        for record in self:
            final_date = record._get_final_date()
            for workorder in record.workorder_ids:
                desc_wo = str(record.name) + '-' + str(workorder.workcenter_id.name) + '-' + str(workorder.name)
                for time in workorder.time_ids:
                    if time.overall_duration:
                        varamount += time.working_duration * workorder.workcenter_id.costs_hour / 60 * workorder.workcenter_id.costs_overhead_variable_percentage / 100
                        fixedamount += (time.setup_duration + time.teardown_duration) * workorder.workcenter_id.costs_hour_fixed / 60 * workorder.workcenter_id.costs_overhead_fixed_percentage / 100
                    else:
                        varamount += time.duration * workorder.workcenter_id.costs_hour / 60 * workorder.workcenter_id.costs_overhead_variable_percentage / 100
                # fixed direct overhead cost posting
                if fixedamount:
                    id_created= self.env['account.analytic.line'].create({
                        'name': desc_wo,
                        'account_id': workorder.workcenter_id.analytic_account_id.id,
                        'ref': "OVH fixed direct costs",
                        'date': final_date,
                        'product_id': record.product_id.id,
                        'amount': fixedamount,
                        'unit_amount': workorder.qty_output_wo,
                        'product_uom_id': record.product_uom_id.id,
                        'company_id': workorder.workcenter_id.company_id.id,
                        'manufacture_order_id': record.id,
                    })
                # variable direct overhead cost posting
                if varamount:
                    id_created= self.env['account.analytic.line'].create({
                        'name': desc_wo,
                        'account_id': workorder.workcenter_id.analytic_account_id.id,
                        'ref': "OVH variable direct costs",
                        'date': final_date,
                        'product_id': record.product_id.id,
                        'amount': varamount,
                        'unit_amount': workorder.qty_output_wo,
                        'product_uom_id': record.product_uom_id.id,
                        'company_id': workorder.workcenter_id.company_id.id,
                        'manufacture_order_id': record.id,
                    })
            record.ovh_var_direct_cost = varamount
            record.ovh_fixed_direct_cost = fixedamount
        return True

    def _bom_ovh_analytic_postings(self):
        ovhproductcost = 0.0
        ovhcomponentscost = 0.0
        for record in self:
            final_date = record._get_final_date()
            desc_bom = str(record.name)
            ovhproductcost = record.direct_cost * record.bom_id.costs_overhead_product_percentage / 100
            ovhcomponentscost = record.mat_cost * record.bom_id.costs_overhead_components_percentage / 100
            # overhead product cost posting
            if ovhproductcost:
                id_created= self.env['account.analytic.line'].create({
                    'name': desc_bom,
                    'account_id': record.bom_id.analytic_account_id.id,
                    'ref': "OVH production costs",
                    'date': final_date,
                    'product_id': record.product_id.id,
                    'amount': - ovhproductcost,
                    'unit_amount': record.product_qty,
                    'product_uom_id': record.product_uom_id.id,
                    'company_id': record.company_id.id,
                    'manufacture_order_id': record.id,
                })
            # overhead components cost posting
            if ovhcomponentscost:
                id_created= self.env['account.analytic.line'].create({
                    'name': desc_bom,
                    'account_id': record.bom_id.analytic_account_id.id,
                    'ref': "OVH components costs",
                    'date': final_date,
                    'product_id': record.product_id.id,
                    'amount': - ovhcomponentscost,
                    'unit_amount': record.product_qty,
                    'product_uom_id': record.product_uom_id.id,
                    'company_id': record.company_id.id,
                    'manufacture_order_id': record.id,
                })
            record.ovh_product_cost = ovhproductcost
            record.ovh_components_cost = ovhcomponentscost
        return True
