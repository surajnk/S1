# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    
    # standard unit costs
    std_prod_cost = fields.Float('Current Standard Cost', digits='Product Price', compute='calculate_standard_costs', store=True, group_operator="avg")
    std_mat_cost = fields.Float('Standard Material Unit Cost', digits='Product Price', compute='calculate_standard_costs', store=True, group_operator="avg")
    std_var_cost = fields.Float('Standard Direct Variable Unit Cost', digits='Product Price', compute='calculate_standard_costs', store=True, group_operator="avg")
    std_fixed_cost = fields.Float('Standard Direct Fixed Unit Cost', digits='Product Price', compute='calculate_standard_costs', store=True, group_operator="avg")
    std_direct_cost = fields.Float('Standard Direct Unit Cost', digits='Product Price', compute='calculate_standard_costs', store=True, group_operator="avg")
    std_byproduct_amount = fields.Float('Standard ByProduct Amount', digits='Product Price', compute='calculate_standard_by_product_amount', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.company.currency_id.id)
     # planned costs
    planned_mat_cost = fields.Float('Planned Material Cost', digits='Product Price', compute='calculate_planned_material_cost', store=True)
    planned_mat_cost_unit = fields.Float('Planned Material Unit Cost', digits='Product Price', compute='calculate_planned_material_cost', store=True, group_operator="avg")
    planned_var_cost = fields.Float('Planned Direct Variable Cost', digits='Product Price', compute='calculate_planned_costs', store=True)
    planned_var_cost_unit = fields.Float('Planned Direct Variable Unit Cost', digits='Product Price', compute='calculate_planned_costs', store=True, group_operator="avg")
    planned_fixed_cost = fields.Float('Planned Direct Fixed Cost', digits='Product Price', compute='calculate_planned_costs', store=True)
    planned_fixed_cost_unit = fields.Float('Planned Direct Fixed Unit Cost', digits='Product Price', compute='calculate_planned_costs', store=True, group_operator="avg")
    planned_direct_cost = fields.Float('Planned Direct Cost', digits='Product Price', compute='calculate_planned_costs', store=True)
    planned_direct_cost_unit = fields.Float('Planned Direct Unit Cost', digits='Product Price', compute='calculate_planned_costs', store=True, group_operator="avg")
    planned_byproduct_amount = fields.Float('Planned ByProduct Amount', digits='Product Price', compute='calculate_planned_by_product_amount', store=True)
    planned_byproduct_amount_unit = fields.Float('Planned ByProduct Unit Amount', digits='Product Price', compute='calculate_planned_by_product_amount', store=True, group_operator="avg")
    # actual costs
    mat_cost = fields.Float('Actual Components Cost', digits='Product Price', compute='calculate_actual_material_cost', store=True)
    mat_cost_unit = fields.Float('Actual Components Unit Cost', digits='Product Price', compute='calculate_actual_material_cost', store=True, group_operator="avg")
    var_cost = fields.Float('Actual Direct Variable Cost', digits='Product Price', compute='calculate_actual_costs', store=True)
    var_cost_unit = fields.Float('Actual Direct Variable Unit Cost', digits='Product Price', compute='calculate_actual_costs', store=True, group_operator="avg")
    fixed_cost = fields.Float('Actual Direct Fixed Cost', digits='Product Price', compute='calculate_actual_costs', store=True)
    fixed_cost_unit = fields.Float('Actual Direct Fixed Unit Cost', digits='Product Price', compute='calculate_actual_costs', store=True, group_operator="avg")
    direct_cost = fields.Float('Actual Full Direct Cost', digits='Product Price', compute='calculate_actual_costs', store=True)
    direct_cost_unit = fields.Float('Actual Full Direct Unit Cost', digits='Product Price', compute='calculate_actual_costs', store=True, group_operator="avg")
    by_product_amount = fields.Float('Actual ByProduct Amount', digits='Product Price', compute='calculate_actual_by_product_amount', store=True)
    by_product_amount_unit = fields.Float('Actual ByProduct Unit Amount', digits='Product Price', compute='calculate_actual_by_product_amount', store=True, group_operator="avg")
    # delta costs = actual - planned
    delta_mat_cost = fields.Float('Delta Components Cost', digits='Product Price', compute='calculate_delta_costs', store=True)
    delta_var_cost = fields.Float('Delta Direct Variable Cost', digits='Product Price', compute='calculate_delta_costs', store=True)
    delta_fixed_cost = fields.Float('Delta Direct Fixed Cost', digits='Product Price', compute='calculate_delta_costs', store=True)
    delta_direct_cost = fields.Float('Delta Direct Cost', digits='Product Price', compute='calculate_delta_costs', store=True)
    delta_byproduct = fields.Float('Delta ByProduct Amount', digits='Product Price', compute='calculate_delta_costs', store=True)
    
    wip_amount = fields.Float('WIP Amount', digits='Product Price',  compute='calculate_wip_amount', store=True)
    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', readonly=True, states={'draft': [('readonly', False)]})
    
    def _get_qty_produced(self):
        qty_produced = 1.0
        for production in self:
            if production.product_id and production.product_qty:
                if not production.qty_producing == 0.0:
                    qty_produced = production.product_uom_id._compute_quantity(production.qty_producing, production.product_id.product_tmpl_id.uom_id)
                else:
                    qty_produced = production.product_uom_qty
        return qty_produced

    # standard costs calculation
    @api.depends('bom_id')     
    def calculate_standard_by_product_amount(self):
        byproductamount = 0.0
        for production in self:
            if production.bom_id:
                for byproduct_id in production.bom_id.byproduct_ids:
                    byproductamount += byproduct_id.product_id.standard_price * byproduct_id.product_qty
            production.std_byproduct_amount = byproductamount
        return True
    
    @api.depends('bom_id','std_byproduct_amount')
    def calculate_standard_costs(self):
        costmat = 0.0
        costlab = 0.0
        costfixed = 0.0
        for production in self:
            if production.bom_id:
                result, result2 = production.bom_id.explode(production.product_id, 1)
                for sbom, sbom_data in result2:
                    costmat += sbom.product_id.standard_price * sbom_data['qty']
                for operation in production.bom_id.operation_ids:
                        costlab += (operation.time_cycle/60) * operation.workcenter_id.costs_hour
                        costfixed += (operation.workcenter_id.time_stop + operation.workcenter_id.time_start) * operation.workcenter_id.costs_hour_fixed / 60
            production.std_prod_cost = production.product_id.standard_price
            _logger.info("STANDARD PROD COST'%s'",production.std_prod_cost)
            production.std_mat_cost = costmat
            _logger.info("STANDARD MAT COST'%s'",production.std_mat_cost)
            production.std_var_cost = costlab
            _logger.info("STANDARD VAR COST'%s'",production.std_var_cost)
            production.std_fixed_cost = costfixed
            _logger.info("STANDARD FIXED COST'%s'",production.std_fixed_cost)
            production.std_direct_cost = costlab + costfixed + costmat - production.std_byproduct_amount
            _logger.info("STANDARD DIRECT COST'%s'",production.std_direct_cost)
        return True
  
    # planned costs calculation
    @api.depends('move_finished_ids.state','state','product_id','product_uom_qty')
    def calculate_planned_by_product_amount(self):
        plannedreceiptamount = 0.0
        for production in self:
            if production.state == "confirmed":
                moves = production.move_finished_ids.filtered(lambda r: r.state != 'cancel')
                for move in moves:
                    plannedreceiptamount += move.product_id.standard_price * move.product_qty
                if production.product_uom_qty and plannedreceiptamount > 0.0:
                    production.planned_byproduct_amount = plannedreceiptamount - production.std_prod_cost * production.product_uom_qty
                    production.planned_byproduct_amount_unit = production.planned_byproduct_amount/production.product_uom_qty
        return True

    @api.depends('move_raw_ids.state','state','product_id','product_uom_qty')
    def calculate_planned_material_cost(self):
        plannedmatamount = 0.0
        for production in self:
            if production.state == "confirmed":
                moves = production.move_raw_ids.filtered(lambda r: r.state != 'cancel')
                for move in moves:
                    plannedmatamount += move.product_id.standard_price * move.product_qty
                production.planned_mat_cost = plannedmatamount
                production.planned_mat_cost_unit = plannedmatamount/production.product_uom_qty
        return True
        
    @api.depends('workorder_ids','state','product_id','product_uom_qty')
    def calculate_planned_costs(self):
        plannedvaramount = 0.0
        plannedfixedamount = 0.0
        duration_expected_working = 0.0
        for production in self:
            if production.state == "confirmed":
                for workorder in production.workorder_ids:
                    duration_expected_working = (workorder.duration_expected - workorder.workcenter_id.time_start - workorder.workcenter_id.time_stop) * workorder.workcenter_id.time_efficiency / 100.0
                    if duration_expected_working > 0:
                        plannedvaramount += duration_expected_working * workorder.workcenter_id.costs_hour / 60
                        plannedfixedamount += (workorder.workcenter_id.time_start + workorder.workcenter_id.time_stop) * workorder.workcenter_id.time_efficiency / 100.0 * workorder.workcenter_id.costs_hour_fixed / 60
                    else:
                        plannedfixedamount += workorder.duration_expected * workorder.workcenter_id.costs_hour_fixed / 60
                production.planned_var_cost = plannedvaramount 
                production.planned_var_cost_unit = plannedvaramount / production.product_uom_qty
                production.planned_fixed_cost = plannedfixedamount 
                production.planned_fixed_cost_unit = plannedfixedamount / production.product_uom_qty
                production.planned_direct_cost = plannedvaramount + plannedfixedamount + production.planned_mat_cost - production.planned_byproduct_amount
                production.planned_direct_cost_unit = (plannedvaramount + plannedfixedamount) / production.product_uom_qty + production.planned_mat_cost_unit - production.planned_byproduct_amount_unit
        return True
    
    # actual costs calculation
    @api.depends('move_raw_ids.state','product_id','qty_producing','product_qty')
    def calculate_actual_material_cost(self):
        matamount = 0.0
        for production in self:
            moves = production.move_raw_ids.filtered(lambda r: r.state == 'done')
            for move in moves:
                matamount += move.product_id.standard_price * move.product_qty
            qty_produced = production._get_qty_produced()
            production.mat_cost = matamount
            production.mat_cost_unit = matamount/qty_produced
        return True
   
    @api.depends('move_finished_ids.state','product_id','qty_producing','product_qty')  
    def calculate_actual_by_product_amount(self):
        receiptamount = 0.0
        for production in self:
            moves = production.move_finished_ids.filtered(lambda r: r.state == 'done')
            for move in moves:
                receiptamount += move.product_id.standard_price * move.product_qty
            qty_produced = production._get_qty_produced()
            if receiptamount > 0.0:
                production.by_product_amount = receiptamount - production.std_prod_cost * qty_produced
                production.by_product_amount_unit = production.by_product_amount/qty_produced
        return True
    
    @api.depends('workorder_ids.time_ids','product_id','qty_producing','product_qty','by_product_amount') 
    def calculate_actual_costs(self):
        varamount = 0.0
        fixedamount = 0.0
        for production in self:
            for workorder in production.workorder_ids:
                for time in workorder.time_ids:
                    if time.overall_duration:
                        varamount += time.working_duration * workorder.workcenter_id.costs_hour / 60
                        fixedamount += (time.setup_duration + time.teardown_duration) * workorder.workcenter_id.costs_hour_fixed / 60
                    else:
                        varamount += time.duration * workorder.workcenter_id.costs_hour / 60
            qty_produced = production._get_qty_produced()
            production.var_cost = varamount 
            production.var_cost_unit = varamount/qty_produced
            production.fixed_cost = fixedamount
            production.fixed_cost_unit = fixedamount/qty_produced
            production.direct_cost = fixedamount + varamount + production.mat_cost - production.by_product_amount
            production.direct_cost_unit = production.direct_cost/qty_produced
        return True
    
    # delta costs calculation
    @api.depends('mat_cost_unit','var_cost_unit','direct_cost_unit','by_product_amount')
    def calculate_delta_costs(self):
        for production in self:
            production.delta_mat_cost = production.mat_cost - production.planned_mat_cost
            production.delta_var_cost = production.var_cost - production.planned_var_cost
            production.delta_fixed_cost = production.fixed_cost - production.planned_fixed_cost
            production.delta_direct_cost = production.direct_cost - production.planned_direct_cost
            production.delta_byproduct = production.by_product_amount - production.planned_byproduct_amount
        return True
    
    # WIP calculation
    @api.depends('state','var_cost','mat_cost','fixed_cost')
    def calculate_wip_amount(self):
        wipamount = 0.0
        for production in self:
            if production.state != 'done':
                wipamount = production.mat_cost + production.var_cost + production.fixed_cost
            production.wip_amount = wipamount
        return True
        
        
        
        
        
        
        