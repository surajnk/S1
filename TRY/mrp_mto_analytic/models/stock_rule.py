# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from datetime import datetime
import random


class StockRule(models.Model):
    _inherit = 'stock.rule'

    # purchase_stock module
    # MTO purchase orders to be created as new document
    def _make_po_get_domain(self, company_id, values, partner):
        return (("id", "=", 0),)

    # mrp module
    # prepare data for MO creation
    def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom):
        date_requirement = False
        confirmed_date = False
        res = super()._prepare_mo_vals(product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom)
        res.update({'analytic_account_id': values.get('account_analytic_id', False)})
        source_sale = self.env['sale.order'].search([('name', '=', origin)], limit=1)
        if source_sale:
            source_sale = source_sale[0]
            calendar = source_sale.warehouse_id.calendar_id
            date_requirement = source_sale.commitment_date or source_sale.expected_date
            date_requirement = date_requirement - relativedelta(days=company_id.security_lead)
            date_requirement = calendar.plan_hours(-1, date_requirement, True)
        source_mo = self.env['mrp.production'].search([('name', '=', origin)], limit=1)
        if source_mo:
            confirmed_date = source_mo.x_mrp_confirmed_date or fields.Date.to_date(source_mo.date_planned_start_pivot)
            if confirmed_date:
                date_requirement = datetime.combine(confirmed_date, datetime.min.time())
            else:
                date_requirement = source_mo.date_planned_start_pivot
        if date_requirement:
            date_start = self._get_planned_pivot_start_date(date_requirement, product_id, company_id, location_id)
        else:
            date_start = datetime.now()
        res.update({'date_planned_start_pivot': date_start})
        res.update({'date_planned_start': date_start})
        return res

    def _get_planned_pivot_start_date(self, date_finished, product_id, company_id, location_id):
        date_start = False
        warehouse_id = location_id.get_warehouse()
        for production in self:
            date_start = date_finished - relativedelta(days=product_id.produce_delay + 1)
            if company_id.manufacturing_lead > 0:
                date_start = date_start - relativedelta(days=company_id.manufacturing_lead + 1)
            if warehouse_id.calendar_id:
                calendar = warehouse_id.calendar_id
                date_start = calendar.plan_days(- product_id.produce_delay - 1, date_finished, True)
                if company_id.manufacturing_lead > 0:
                    date_start = calendar.plan_days(- company_id.manufacturing_lead - 1, date_start, True)
            if date_finished == date_start:
                date_start = date_finished + relativedelta(hours= -1)
        return date_start
