# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime
from datetime import date
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'


    # @api.constrains('state')
    # def get_actual_posting(self):
    #     for record in self:
    #         if record.state in [('done'),('cancel')]:
    #             # record._direct_cost_postings()
    #             record._direct_lab_ovh_cost_postings()
    #     return True

    def _update_direct_lab_ovh_cost_postings(self, blocktime_id):
        """Upsert a single account.move per productivity blocktime (time_id).
        This will create or update a single move identified by time_id, so manual edits
        of blocktimes do not create duplicated moves.
        Debit destination is the finished product category's single WIP account (fallbacks applied).
        """
        for record in self:
            # RESET totals per record
            total_working_duration = total_fixed_duration = 0.0
            amount_working = lab_cost = ovh_cost = amount_fixed = 0.0
            final_date = False

            _logger.info("DEBUG: _update_direct_lab_ovh_cost_postings for WO %s (MO %s)",
                         record.name, getattr(record.production_id, 'name', False))

            desc_wo = "%s-%s-%s" % (
                record.production_id.name or '',
                record.workcenter_id.name or '',
                record.name or '',
            )

            # Most recent time end for header date
            last_time = self.env['mrp.workcenter.productivity'].search(
                [('workorder_id', '=', record.id), ('date_end', '!=', False)],
                order="date_end desc", limit=1
            )
            final_date = last_time.date_end.date() if last_time else date.today()
            analytic_account = record.production_id.analytic_account_id.id

            # accumulate durations
            for time in record.time_ids:
                if time.overall_duration:
                    total_working_duration += time.working_duration
                    total_fixed_duration += time.setup_duration + time.teardown_duration
                else:
                    total_working_duration += time.duration

            amount_fixed = round((total_fixed_duration * record.workcenter_id.costs_hour_fixed) / 60, 2)
            lab_cost = round((total_working_duration * record.workcenter_id.labor_costs_hour) / 60, 2)
            ovh_cost = round((total_working_duration * record.workcenter_id.overhead_costs_hour) / 60, 2)
            amount_working = lab_cost + ovh_cost

            journal = record.production_id.company_id.manufacturing_journal_id
            if not journal:
                raise UserError(_("Manufacturing Journal is not defined on the Company %s")
                                % record.production_id.company_id.name)

            # --------- UPSERT HEADER (one per blocktime) ----------
            move = self.env['account.move'].search([('time_id', '=', blocktime_id)], limit=1)
            if move:
                # If posted, unpost to allow re-write
                if move.state == 'posted':
                    move.button_draft()
                # remove existing lines for rebuild
                move.line_ids.unlink()
                move.write({
                    'date': final_date,
                    'ref': "Direct Variable Costs",
                    'journal_id': journal.id,
                    'company_id': record.workcenter_id.company_id.id,
                    'time_id': blocktime_id,
                })
            else:
                move = self.env['account.move'].create({
                    'journal_id': journal.id,
                    'date': final_date,
                    'ref': "Direct Variable Costs",
                    'company_id': record.workcenter_id.company_id.id,
                    'time_id': blocktime_id,
                })

            # CREDIT (Lab)
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'move_id': move.id,
                'account_id': record.workcenter_id.costing_account_id.id,
                'product_id': record.production_id.product_id.id,
                'name': desc_wo,
                'quantity': record.qty_output_wo,
                'product_uom_id': record.production_id.product_uom_id.id,
                'credit': lab_cost,
                'debit': 0.0,
                'manufacture_order_id': record.production_id.id,
                'time_id': blocktime_id,
            })

            # CREDIT (Overhead)
            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'move_id': move.id,
                'account_id': record.workcenter_id.ovh_costing_account_id.id,
                'product_id': record.production_id.product_id.id,
                'name': desc_wo,
                'quantity': record.qty_output_wo,
                'product_uom_id': record.production_id.product_uom_id.id,
                'credit': ovh_cost,
                'debit': 0.0,
                'manufacture_order_id': record.production_id.id,
                'time_id': blocktime_id,
            })

            # DEBIT (use product category single WIP account first, fallback to production property)
            categ = record.production_id.product_id.categ_id
            wip_candidate = False
            if categ:
                wip_candidate = getattr(categ, 'wip_account_id', False) or getattr(categ, 'x_property_account_inventory_categ_id', False)
            wip_in_id = (wip_candidate.id if wip_candidate else False) or record.production_id.product_id.property_stock_production.valuation_in_account_id.id

            self.env['account.move.line'].with_context(check_move_validity=False).create({
                'move_id': move.id,
                'account_id': wip_in_id,
                'analytic_account_id': analytic_account,
                'product_id': record.production_id.product_id.id,
                'name': desc_wo,
                'quantity': record.qty_output_wo,
                'product_uom_id': record.production_id.product_uom_id.id,
                'credit': 0.0,
                'debit': amount_working,
                'manufacture_order_id': record.production_id.id,
                'time_id': blocktime_id,
            })

            if move.state != 'posted':
                move.post()
        return True

    # def _update_direct_lab_ovh_cost_postings(self, blocktime_id):
    #     for record in self:
    #         # RESET totals per record
    #         total_working_duration = total_fixed_duration = 0.0
    #         amount_working = lab_cost = ovh_cost = amount_fixed = 0.0
    #         final_date = False

    #         _logger.info("DEBUGGING JOURNAL ISSUE")
    #         _logger.info("Production: %s", record.production_id)
    #         _logger.info("Company: %s", record.production_id.company_id)
    #         _logger.info("Manufacturing Journal: %s", record.production_id.company_id.manufacturing_journal_id)

    #         desc_wo = "%s-%s-%s" % (
    #             record.production_id.name or '',
    #             record.workcenter_id.name or '',
    #             record.name or '',
    #         )

    #         # Most recent time end (for the header date)
    #         last_time = self.env['mrp.workcenter.productivity'].search(
    #             [('workorder_id', '=', record.id), ('date_end', '!=', False)],
    #             order="date_end desc", limit=1
    #         )
    #         final_date = last_time.date_end.date() if last_time else date.today()
    #         analytic_account = record.production_id.analytic_account_id.id

    #         # durations
    #         for time in record.time_ids:
    #             if time.overall_duration:
    #                 total_working_duration += time.working_duration
    #                 total_fixed_duration += time.setup_duration + time.teardown_duration
    #             else:
    #                 total_working_duration += time.duration

    #         amount_fixed = round((total_fixed_duration * record.workcenter_id.costs_hour_fixed) / 60, 2)
    #         lab_cost    = round((total_working_duration * record.workcenter_id.labor_costs_hour) / 60, 2)
    #         ovh_cost    = round((total_working_duration * record.workcenter_id.overhead_costs_hour) / 60, 2)
    #         amount_working = lab_cost + ovh_cost

    #         journal = record.production_id.company_id.manufacturing_journal_id
    #         if not journal:
    #             raise UserError(_("Manufacturing Journal is not defined on the Company %s")
    #                             % record.production_id.company_id.name)

    #         # --------- UPSERT HEADER (one per blocktime) ----------
    #         move = self.env['account.move'].search([('time_id', '=', blocktime_id)], limit=1)
    #         if move:
    #             if move.state == 'posted':
    #                 move.button_draft()
    #             # clear existing lines for this blocktime and rebuild
    #             move.line_ids.unlink()
    #             move.write({
    #                 'date': final_date,
    #                 'ref': "Direct Variable Costs",  # keep stable ref
    #                 'journal_id': journal.id,
    #                 'company_id': record.workcenter_id.company_id.id,
    #                 'time_id': blocktime_id,   # ensure set
    #             })
    #         else:
    #             move = self.env['account.move'].create({
    #                 'journal_id': journal.id,
    #                 'date': final_date,
    #                 'ref': "Direct Variable Costs",
    #                 'company_id': record.workcenter_id.company_id.id,
    #                 'time_id': blocktime_id,     # <-- CRUCIAL: key for upsert
    #             })

    #         # CREDIT (Lab)
    #         self.env['account.move.line'].with_context(check_move_validity=False).create({
    #             'move_id': move.id,
    #             'account_id': record.workcenter_id.costing_account_id.id,
    #             'product_id': record.production_id.product_id.id,
    #             'name': desc_wo,
    #             'quantity': record.qty_output_wo,
    #             'product_uom_id': record.production_id.product_uom_id.id,
    #             'credit': lab_cost,
    #             'debit': 0.0,
    #             'manufacture_order_id': record.production_id.id,
    #             'time_id': blocktime_id,
    #         })

    #         # CREDIT (Overhead)
    #         self.env['account.move.line'].with_context(check_move_validity=False).create({
    #             'move_id': move.id,
    #             'account_id': record.workcenter_id.ovh_costing_account_id.id,
    #             'product_id': record.production_id.product_id.id,
    #             'name': desc_wo,
    #             'quantity': record.qty_output_wo,
    #             'product_uom_id': record.production_id.product_uom_id.id,
    #             'credit': ovh_cost,
    #             'debit': 0.0,
    #             'manufacture_order_id': record.production_id.id,
    #             'time_id': blocktime_id,
    #         })

    #         # DEBIT (WIP-in of Workcenter; fallback to product.production valuation_in)
    #         wip_in_id = (
    #             record.workcenter_id.location_id
    #             and record.workcenter_id.location_id.valuation_in_account_id
    #             and record.workcenter_id.location_id.valuation_in_account_id.id
    #         ) or record.production_id.product_id.property_stock_production.valuation_in_account_id.id

    #         self.env['account.move.line'].with_context(check_move_validity=False).create({
    #             'move_id': move.id,
    #             'account_id': wip_in_id,
    #             'analytic_account_id': analytic_account,
    #             'product_id': record.production_id.product_id.id,
    #             'name': desc_wo,
    #             'quantity': record.qty_output_wo,
    #             'product_uom_id': record.production_id.product_uom_id.id,
    #             'credit': 0.0,
    #             'debit': amount_working,
    #             'manufacture_order_id': record.production_id.id,
    #             'time_id': blocktime_id,
    #         })

    #         if move.state != 'posted':
    #             move.post()
    #     return True

    
    # def _update_direct_lab_ovh_cost_postings(self,blocktime_id):
    #     for record in self:
    #         total_working_duration = 0.0
    #         total_fixed_duration = 0.0
    #         amount_working = 0.0
    #         lab_cost = 0.0
    #         ovh_cost = 0.0
    #         amount_fixed = 0.0
    #         final_date = False
    #         _logger.info("DEBUGGING JOURNAL ISSUE")
    #         _logger.info("Production: %s", record.production_id)
    #         _logger.info("Company: %s", record.production_id.company_id)
    #         _logger.info("Manufacturing Journal: %s", record.production_id.company_id.manufacturing_journal_id)

    #         desc_wo = str(record.production_id.name or '') + '-' + str(record.workcenter_id.name or '') + '-' + str(record.name or '')
    #         last_time = self.env['mrp.workcenter.productivity'].search([('workorder_id', '=', record.id),('date_end', '!=', False)], order= "date_end desc", limit=1)
    #         if last_time:
    #             final_date = last_time.date_end.date()
    #         else:
    #             final_date = date.today()
    #         analytic_account = record.production_id.analytic_account_id.id
    #         for time in record.time_ids:
    #             if time.overall_duration:
    #                 total_working_duration += time.working_duration
    #                 total_fixed_duration += time.setup_duration + time.teardown_duration
    #             else:
    #                 total_working_duration += time.duration
    #         # amount_working = round((total_working_duration * record.workcenter_id.costs_hour)/ 60, 2)
    #         amount_fixed = round((total_fixed_duration * record.workcenter_id.costs_hour_fixed)/ 60, 2)
    #         lab_cost = round((total_working_duration * record.workcenter_id.labor_costs_hour)/60, 2)
    #         ovh_cost = round((total_working_duration * record.workcenter_id.overhead_costs_hour)/60, 2)
    #         amount_working = lab_cost + ovh_cost
    #         journal = record.production_id.company_id.manufacturing_journal_id
    #         if not journal:
    #             raise UserError(_("Manufacturing Journal is not defined on the Company %s") % record.production_id.company_id.name)

    #         id_created_header = self.env['account.move'].create({
    #             'journal_id' : journal.id,
    #             'date': final_date,
    #             'ref' : "Direct Variable Costs",
    #             'company_id': record.workcenter_id.company_id.id,
    #         })
    #         id_lab_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
    #             'move_id' : id_created_header.id,
    #             'account_id': record.workcenter_id.costing_account_id.id,
    #             'product_id': record.production_id.product_id.id,
    #             'name' : desc_wo,
    #             'quantity': record.qty_output_wo,
    #             'product_uom_id': record.production_id.product_uom_id.id,
    #             'credit': lab_cost,
    #             'debit': 0.0,
    #             'manufacture_order_id': record.production_id.id,
    #         })
    #         id_ovh_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
    #             'move_id' : id_created_header.id,
    #             'account_id': record.workcenter_id.ovh_costing_account_id.id,
    #             'product_id': record.production_id.product_id.id,
    #             'name' : desc_wo,
    #             'quantity': record.qty_output_wo,
    #             'product_uom_id': record.production_id.product_uom_id.id,
    #             'credit': ovh_cost,
    #             'debit': 0.0,
    #             'manufacture_order_id': record.production_id.id,
    #         })
    #         id_debit_item= self.env['account.move.line'].with_context(check_move_validity=False).create({
    #             'move_id' : id_created_header.id,
    #             'account_id' : (
    #                                 record.workcenter_id.location_id and 
    #                                 record.workcenter_id.location_id.valuation_in_account_id and 
    #                                 record.workcenter_id.location_id.valuation_in_account_id.id
    #                             ) or record.production_id.product_id.property_stock_production.valuation_in_account_id.id,
    #             # 'account_id': record.production_id.product_id.property_stock_production.valuation_in_account_id.id,
    #             'analytic_account_id' : analytic_account,
    #             'product_id': record.production_id.product_id.id,
    #             'name' : desc_wo,
    #             'quantity': record.qty_output_wo,
    #             'product_uom_id': record.production_id.product_uom_id.id,
    #             'credit': 0.0,
    #             'debit': amount_working,
    #             'manufacture_order_id': record.production_id.id,
    #         })
    #         _logger.info("DEBIT ITEM '%s',",id_debit_item)  
    #         id_created_header.post()
    #     return True

    def _direct_lab_ovh_cost_postings(self):
        """
        Final posting for labour + overhead.
        Uses single category WIP (fallbacks) and creates a single account.move with:
          - credit lines for lab & ovh (if any)
          - a single debit line to WIP for their sum
        """
        for record in self:
            # reset per record
            total_working_duration = total_fixed_duration = 0.0
            amount_working = lab_cost = ovh_cost = amount_fixed = 0.0
            final_date = False

            desc_wo = "%s-%s-%s" % (
                record.production_id.name or '',
                record.workcenter_id.name or '',
                record.name or '',
            )
            last_time = self.env['mrp.workcenter.productivity'].search([('workorder_id', '=', record.id), ('date_end', '!=', False)], order="date_end desc", limit=1)
            final_date = last_time.date_end.date() if last_time else date.today()
            analytic_account = record.production_id.analytic_account_id.id

            for time in record.time_ids:
                if time.overall_duration:
                    total_working_duration += time.working_duration
                    total_fixed_duration += time.setup_duration + time.teardown_duration
                else:
                    total_working_duration += time.duration

            amount_fixed = round((total_fixed_duration * record.workcenter_id.costs_hour_fixed) / 60, 2)
            lab_cost = round((total_working_duration * record.workcenter_id.labor_costs_hour) / 60, 2)
            ovh_cost = round((total_working_duration * record.workcenter_id.overhead_costs_hour) / 60, 2)
            amount_working = lab_cost + ovh_cost

            lines = []
            if amount_working:
                acc_var = (record.production_id.company_id.labour_cost_account_id
                           if record.workcenter_id.wc_type == "H"
                           else record.production_id.company_id.machine_run_cost_account_id)
                lines.append(('CREDIT', acc_var, amount_working))

            if amount_fixed:
                acc_fix = (record.production_id.company_id.labour_fixed_cost_account_id
                           if record.workcenter_id.wc_type == "H"
                           else record.production_id.company_id.machine_run_fixed_cost_account_id)
                lines.append(('CREDIT', acc_fix, amount_fixed))

            if lines:
                id_created_header = self.env['account.move'].create({
                    'journal_id': record.production_id.company_id.manufacturing_journal_id.id,
                    'date': final_date,
                    'ref': "Direct Variable/Fixed Costs",
                    'company_id': record.workcenter_id.company_id.id,
                })
                total_debit = 0.0
                for _, acc, amt in lines:
                    self.env['account.move.line'].with_context(check_move_validity=False).create({
                        'move_id': id_created_header.id,
                        'account_id': acc.id,
                        'product_id': record.production_id.product_id.id,
                        'name': desc_wo,
                        'quantity': record.qty_output_wo,
                        'product_uom_id': record.production_id.product_uom_id.id,
                        'credit': amt,
                        'debit': 0.0,
                        'manufacture_order_id': record.production_id.id,
                    })
                    total_debit += amt

                # compute category WIP (single field) fallback logic
                categ = record.production_id.product_id.categ_id
                wip_candidate = False
                if categ:
                    wip_candidate = getattr(categ, 'wip_account_id', False) or getattr(categ, 'x_property_account_inventory_categ_id', False)
                wip_in_id = (wip_candidate.id if wip_candidate else False) or record.production_id.product_id.property_stock_production.valuation_in_account_id.id

                self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': wip_in_id,
                    'analytic_account_id': analytic_account,
                    'product_id': record.production_id.product_id.id,
                    'name': desc_wo,
                    'quantity': record.qty_output_wo,
                    'product_uom_id': record.production_id.product_uom_id.id,
                    'credit': 0.0,
                    'debit': total_debit,
                    'manufacture_order_id': record.production_id.id,
                })
                id_created_header.post()


            # id_created_header = self.env['account.move'].create({
            #     'journal_id' : record.production_id.company_id.manufacturing_journal_id.id,
            #     'date': final_date,
            #     'ref' : "Direct Variable Costs",
            #     'company_id': record.workcenter_id.company_id.id,
            #     'time_id' : last_time.id,
            # })
            # id_lab_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
            #     'move_id' : id_created_header.id,
            #     'account_id': record.workcenter_id.costing_account_id.id,
            #     'product_id': record.production_id.product_id.id,
            #     'name' : desc_wo,
            #     'quantity': record.qty_output_wo,
            #     'product_uom_id': record.production_id.product_uom_id.id,
            #     'credit': lab_cost,
            #     'debit': 0.0,
            #     'manufacture_order_id': record.production_id.id,
            #     'time_id' : last_time.id,
            # })
            # id_ovh_credit_item = self.env['account.move.line'].with_context(check_move_validity=False).create({
            #     'move_id' : id_created_header.id,
            #     'account_id': record.workcenter_id.ovh_costing_account_id.id,
            #     'product_id': record.production_id.product_id.id,
            #     'name' : desc_wo,
            #     'quantity': record.qty_output_wo,
            #     'product_uom_id': record.production_id.product_uom_id.id,
            #     'credit': ovh_cost,
            #     'debit': 0.0,
            #     'manufacture_order_id': record.production_id.id,
            #     'time_id' : last_time.id,
            # })
            # id_debit_item= self.env['account.move.line'].with_context(check_move_validity=False).create({
            #     'move_id' : id_created_header.id,
            #     'account_id' : (
            #                         record.workcenter_id.location_id and 
            #                         record.workcenter_id.location_id.valuation_in_account_id and 
            #                         record.workcenter_id.location_id.valuation_in_account_id.id
            #                     ) or record.production_id.product_id.property_stock_production.valuation_in_account_id.id,
            #     # 'account_id': record.production_id.product_id.property_stock_production.valuation_in_account_id.id,
            #     'analytic_account_id' : analytic_account,
            #     'product_id': record.production_id.product_id.id,
            #     'name' : desc_wo,
            #     'quantity': record.qty_output_wo,
            #     'product_uom_id': record.production_id.product_uom_id.id,
            #     'credit': 0.0,
            #     'debit': amount_working,
            #     'manufacture_order_id': record.production_id.id,
            #     'time_id' : last_time.id,
            # })
            # _logger.info("DEBIT ITEM '%s',",id_debit_item)  
            # id_created_header.post()
        return True

    # production direct cost posting
    def _direct_cost_postings(self):
        """
        Keep merged behavior for direct cost postings (var + fixed) — single header.
        """
        for record in self:
            # reset per record
            total_working_duration = total_fixed_duration = 0.0
            amount_working = amount_fixed = 0.0
            final_date = False

            desc_wo = "%s-%s-%s" % (
                record.production_id.name or '',
                record.workcenter_id.name or '',
                record.name or '',
            )
            last_time = self.env['mrp.workcenter.productivity'].search([('workorder_id', '=', record.id), ('date_end', '!=', False)], order="date_end desc", limit=1)
            final_date = last_time.date_end.date() if last_time else date.today()
            analytic_account = record.production_id.analytic_account_id.id or record.workcenter_id.analytic_account_id.id

            for time in record.time_ids:
                if time.overall_duration:
                    total_working_duration += time.working_duration
                    total_fixed_duration += time.setup_duration + time.teardown_duration
                else:
                    total_working_duration += time.duration

            amount_working = round((total_working_duration * record.workcenter_id.costs_hour) / 60, 2)
            amount_fixed = round((total_fixed_duration * record.workcenter_id.costs_hour_fixed) / 60, 2)

            lines = []
            if amount_working:
                acc_var = (record.production_id.company_id.labour_cost_account_id
                           if record.workcenter_id.wc_type == "H"
                           else record.production_id.company_id.machine_run_cost_account_id)
                lines.append(('CREDIT', acc_var, amount_working))

            if amount_fixed:
                acc_fix = (record.production_id.company_id.labour_fixed_cost_account_id
                           if record.workcenter_id.wc_type == "H"
                           else record.production_id.company_id.machine_run_fixed_cost_account_id)
                lines.append(('CREDIT', acc_fix, amount_fixed))

            if lines:
                id_created_header = self.env['account.move'].create({
                    'journal_id': record.production_id.company_id.manufacturing_journal_id.id,
                    'date': final_date,
                    'ref': "Direct Variable/Fixed Costs",
                    'company_id': record.workcenter_id.company_id.id,
                })
                total_debit = 0.0
                for _, acc, amt in lines:
                    self.env['account.move.line'].with_context(check_move_validity=False).create({
                        'move_id': id_created_header.id,
                        'account_id': acc.id,
                        'product_id': record.production_id.product_id.id,
                        'name': desc_wo,
                        'quantity': record.qty_output_wo,
                        'product_uom_id': record.production_id.product_uom_id.id,
                        'credit': amt,
                        'debit': 0.0,
                        'manufacture_order_id': record.production_id.id,
                    })
                    total_debit += amt

                # compute category WIP (single field) fallback logic
                categ = record.production_id.product_id.categ_id
                wip_candidate = False
                if categ:
                    wip_candidate = getattr(categ, 'wip_account_id', False) or getattr(categ, 'x_property_account_inventory_categ_id', False)
                wip_in_id = (wip_candidate.id if wip_candidate else False) or record.production_id.product_id.property_stock_production.valuation_in_account_id.id

                self.env['account.move.line'].with_context(check_move_validity=False).create({
                    'move_id': id_created_header.id,
                    'account_id': wip_in_id,
                    'analytic_account_id': analytic_account,
                    'product_id': record.production_id.product_id.id,
                    'name': desc_wo,
                    'quantity': record.qty_output_wo,
                    'product_uom_id': record.production_id.product_uom_id.id,
                    'credit': 0.0,
                    'debit': total_debit,
                    'manufacture_order_id': record.production_id.id,
                })
                id_created_header.post()
        return True
