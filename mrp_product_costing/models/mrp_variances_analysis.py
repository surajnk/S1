# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
from datetime import date
import logging

_logger = logging.getLogger(__name__)



class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def action_variances_postings(self):
        for record in self:
            qty_produced = record._get_qty_produced()
            record._planned_variance_postings(qty_produced)
            record._material_costs_variance_postings(qty_produced)
            record._direct_costs_variance_postings(qty_produced)
        return True

    def action_ind_material_postings(self):
        for record in self:
            qty_produced = record._get_qty_produced()
            record._material_costs_line_postings(qty_produced)
        return True

    def _get_final_date(self):
        final_date = False
        for record in self:
            if record.date_actual_finished_wo:
                final_date = record.date_actual_finished_wo.date()
            else:
                final_date = date.today()
        return final_date

    # production planned variance costs posting
    def _planned_variance_postings(self, quantity):
        standard_cost = 0.0
        planned_cost = 0.0
        for record in self:
            final_date = record._get_final_date()
            standard_cost = record.std_prod_cost
            planned_cost = record.planned_direct_cost_unit
            delta = (planned_cost - standard_cost) * quantity
            desc_bom = str(record.name)
            if delta < 0.0:
                id_created_header = self.env['account.move'].create({
                    'journal_id': record.company_id.manufacturing_journal_id.id,
                    'date': final_date,
                    'ref': "Planned Costs Variance",
                    'company_id': record.company_id.id,
                })
                id_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.company_id.planned_variances_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': - delta,
                    'debit': 0.0,
                    'manufacture_order_id': record.id,
                })
                id_debit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.product_id.property_stock_production.valuation_out_account_id.id,
                    # 'analytic_account_id' : record.bom_id.costs_planned_variances_analytic_account_id.id,
                    'analytic_account_id': record.analytic_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': 0.0,
                    'debit': - delta,
                    'manufacture_order_id': record.id,
                })
                id_created_header.post()
            elif delta > 0.0:
                id_created_header = self.env['account.move'].create({
                    'journal_id': record.company_id.manufacturing_journal_id.id,
                    'date': final_date,
                    'ref': "Planned Costs Variance",
                    'company_id': record.company_id.id,
                })
                id_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.product_id.property_stock_production.valuation_out_account_id.id,
                    'analytic_account_id': record.analytic_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': delta,
                    'debit': 0.0,
                    'manufacture_order_id': record.id,
                })
                id_debit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.company_id.planned_variances_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': 0.0,
                    'debit': delta,
                    'manufacture_order_id': record.id,
                })
                id_created_header.post()
        return True

    def _material_costs_line_postings(self, quantity):
        mat_actual_amount = 0.0
        mat_planned_amount = 0.0
        matamount = 0.0
        receiptamount = 0.0
        by_product_amount = 0.0
        comp_qty = 0.0
        for record in self:
            final_date = record._get_final_date()
            raw_moves = record.move_raw_ids.filtered(lambda r: (r.product_id.type == 'product'))
            for move in raw_moves:
                for line in move.move_line_ids:
                    quatity_val = self.env['stock.quant'].search(
                        [('product_id', '=', move.product_id.id), ('lot_id', '=', line.lot_id.id),
                         ('location_id', '=', line.location_id.id)])
                    #avg_price = (quatity_val.value / quatity_val.available_quantity) * line.qty_done
                    avg_price = (quatity_val.value / quatity_val.quantity) * line.qty_done
                    comp_qty = line.qty_done
                    # matamount += move.product_id.standard_price * move.product_qty
                    matamount += avg_price
                    mat_actual_amount = matamount
                    delta = mat_actual_amount
                    desc_bom = str(line.product_id.name)
                    if delta > 0.0:
                        id_created_header = self.env['account.move'].create({
                            'journal_id': record.company_id.manufacturing_journal_id.id,
                            'date': final_date,
                            'ref': "Material Cost",
                            'company_id': record.company_id.id,
                        })
                        id_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                            'move_id': id_created_header.id,
                            'account_id': line.product_id.categ_id.x_property_account_inventory_categ_id.id,
                            'analytic_account_id': record.analytic_account_id.id,
                            'product_id': line.product_id.id,
                            'name': desc_bom,
                            'quantity': comp_qty,
                            'product_uom_id': line.product_uom_id.id,
                            'credit': delta,
                            'debit': 0.0,
                            'manufacture_order_id': record.id,
                        })
                        id_debit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                            'move_id': id_created_header.id,
                            'account_id': record.product_id.categ_id.property_account_expense_categ_id.id,
                            'product_id': record.product_id.id,
                            'name': str(record.product_id.name),
                            'quantity': comp_qty,
                            'product_uom_id': record.product_uom_id.id,
                            'credit': 0.0,
                            'debit': delta,
                            'manufacture_order_id': record.id,
                        })
                        id_created_header.post()
        return True



    # production material and by product variance costs posting
    def _material_costs_variance_postings(self, quantity):
        mat_actual_amount = 0.0
        mat_planned_amount = 0.0
        matamount = 0.0
        receiptamount = 0.0
        by_product_amount = 0.0
        for record in self:
            _logger.info("INSIDE MATERIAL VARIANCE")
            final_date = record._get_final_date()
            raw_moves = record.move_raw_ids.filtered(lambda r: (r.state == 'done' and r.product_id.type == 'product'))
            for move in raw_moves:
                for line in move.move_line_ids:
                    quatity_val = self.env['stock.quant'].search(
                        [('product_id', '=', move.product_id.id), ('lot_id', '=', line.lot_id.id),
                         ('location_id', '=', line.location_id.id)])

                    if quatity_val.available_quantity:
                        avg_price = (quatity_val.value / quatity_val.available_quantity) * line.qty_done
                    else:
                        avg_price = 0.0
                    matamount += avg_price
                    # avg_price = (quatity_val.value / quatity_val.available_quantity) * line.qty_done
                    # # matamount += move.product_id.standard_price * move.product_qty
                    # matamount += avg_price
            finished_moves = record.move_finished_ids.filtered(
                lambda r: (r.state == 'done' and r.product_id.type == 'product'))
            for move in finished_moves:
                for line in move.move_line_ids:
                    quatity_val = self.env['stock.quant'].search(
                        [('product_id', '=', move.product_id.id), ('lot_id', '=', line.lot_id.id),
                         ('location_id', '=', line.location_id.id)])
                    if quatity_val.available_quantity:
                        avg_finish_price = (quatity_val.value / quatity_val.available_quantity) * line.qty_done
                    else:
                        avg_finish_price = 0.0
                    receiptamount += avg_finish_price
                    # avg_finish_price = (quatity_val.value / quatity_val.available_quantity) * line.qty_done
                    # # receiptamount += move.product_id.standard_price * move.product_qty
                    # receiptamount += avg_finish_price
            if receiptamount > 0.0:
                by_product_amount = receiptamount - record.std_prod_cost * quantity
            mat_actual_amount = matamount - by_product_amount
            mat_planned_amount = (record.planned_mat_cost_unit - record.planned_byproduct_amount_unit) * quantity
            delta = mat_actual_amount - mat_planned_amount
            desc_bom = str(record.name)
            if delta < 0.0:
                id_created_header = self.env['account.move'].create({
                    'journal_id': record.company_id.manufacturing_journal_id.id,
                    'date': final_date,
                    'ref': "Material and By Products Variance",
                    'company_id': record.company_id.id,
                })
                id_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.company_id.material_variances_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': - delta,
                    'debit': 0.0,
                    'manufacture_order_id': record.id,
                })
                id_debit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.product_id.property_stock_production.valuation_out_account_id.id,
                    'analytic_account_id': record.analytic_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': 0.0,
                    'debit': - delta,
                    'manufacture_order_id': record.id,
                })
                id_created_header.post()
            elif delta > 0.0:
                id_created_header = self.env['account.move'].create({
                    'journal_id': record.company_id.manufacturing_journal_id.id,
                    'date': final_date,
                    'ref': "Material and By Products Variance",
                    'company_id': record.company_id.id,
                })
                id_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.product_id.property_stock_production.valuation_out_account_id.id,
                    'analytic_account_id': record.analytic_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': delta,
                    'debit': 0.0,
                    'manufacture_order_id': record.id,
                })
                id_debit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.company_id.material_variances_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': 0.0,
                    'debit': delta,
                    'manufacture_order_id': record.id,
                })
                id_created_header.post()
        return True

    # production direct variance costs posting
    def _direct_costs_variance_postings(self, quantity):
        direct_actual_amount = 0.0
        direct_planned_amount = 0.0
        for record in self:
            final_date = record._get_final_date()
            direct_actual_amount = (record.var_cost_unit + record.fixed_cost_unit) * quantity
            direct_planned_amount = (record.planned_var_cost_unit + record.planned_fixed_cost_unit) * quantity
            delta = direct_actual_amount - direct_planned_amount
            desc_bom = str(record.name)
            if delta < 0.0:
                id_created_header = self.env['account.move'].create({
                    'journal_id': record.company_id.manufacturing_journal_id.id,
                    'date': final_date,
                    'ref': "Direct Costs Variance",
                    'company_id': record.company_id.id,
                })
                id_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.company_id.other_variances_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': - delta,
                    'debit': 0.0,
                    'manufacture_order_id': record.id,
                })
                id_debit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.product_id.property_stock_production.valuation_out_account_id.id,
                    'analytic_account_id': record.analytic_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': 0.0,
                    'debit': - delta,
                    'manufacture_order_id': record.id,
                })
                id_created_header.post()
            elif delta > 0.0:
                id_created_header = self.env['account.move'].create({
                    'journal_id': record.company_id.manufacturing_journal_id.id,
                    'date': final_date,
                    'ref': "Direct Costs Variance",
                    'company_id': record.company_id.id,
                })
                id_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.product_id.property_stock_production.valuation_out_account_id.id,
                    'analytic_account_id': record.analytic_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': delta,
                    'debit': 0.0,
                    'manufacture_order_id': record.id,
                })
                id_debit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': record.company_id.other_variances_account_id.id,
                    'product_id': record.product_id.id,
                    'name': desc_bom,
                    'quantity': quantity,
                    'product_uom_id': record.product_uom_id.id,
                    'credit': 0.0,
                    'debit': delta,
                    'manufacture_order_id': record.id,
                })
                id_created_header.post()
        return True
