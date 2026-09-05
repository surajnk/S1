# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, time, timedelta
from odoo.exceptions import UserError


class MrpDdiSTCreation(models.TransientModel):
    _name = 'mrp.ddi.st.creation'
    _description = "Distribution Deployment Stock Transfer Creation"


    def _default_ddi_ids(self):
        return self.env['mrp.distribution.deployment'].browse(self.env.context.get('active_ids'))

    ddi_ids = fields.Many2many("mrp.distribution.deployment", string='Distribution Deployment Items', default=lambda self: self._default_ddi_ids())


    def _check_warehouses(self):
        warehouses = self.ddi_ids.mapped('warehouse_id')
        if len(warehouses) != 1:
            raise UserError(_('Warehouse is not the same for all selected items'))
        supply_warehouses = self.ddi_ids.mapped('supply_warehouse_id')
        if len(supply_warehouses) != 1:
            raise UserError(_('Supply Warehouse is not the same for all selected items'))
        return True

    def _check_version(self):
        versions = self.ddi_ids.mapped('origin')
        if len(versions) != 1:
            raise UserError(_('Version is not the same for all selected items'))
        return True

    def get_stock_transfer_document(self):
        if any(ddi_id.state != 'draft' for ddi_id in self.ddi_ids):
            raise UserError(_('All selected items are to be in draft status'))
        self._check_warehouses()
        self._check_version()
        warehouse_id = self.ddi_ids.mapped('warehouse_id')[0]
        supply_warehouse_id = self.ddi_ids.mapped('supply_warehouse_id')[0]
        first_pir_id = self.ddi_ids.mapped('pir_id')[0]
        date_planned = min(self.ddi_ids.mapped('date_planned'))
        purchase_lead_time = warehouse_id.company_id.days_to_purchase
        date = date_planned - timedelta(days=purchase_lead_time)
        id_stock_transfer = self.env['stock.transfer'].create({
            'company_id': first_pir_id.company_id.id,
            'origin': 'DRP: ' + first_pir_id.origin.name,
            'user_id': first_pir_id.origin.user_id.id,
            'warehouse_id': warehouse_id.id,
            'source_warehouse_id': supply_warehouse_id.id,
            'date_planned': date_planned,
            'date': date,
        })
        for ddi_id in self.ddi_ids:
            id_stock_transfer_item = self.env['stock.transfer.line'].create({
                'stock_transfer_id': id_stock_transfer.id,
                'product_id': ddi_id.product_id.id,
                'name': ddi_id.product_id.name,
                'product_uom': ddi_id.product_uom_id.id,
                'product_qty': ddi_id.product_qty,
                'pir_id': ddi_id.pir_id.id,
            })
            ddi_id.state = 'done'
            ddi_id.date = date
            ddi_id.pir_id.stock_transfer_id = id_stock_transfer.id
            ddi_id.stock_transfer_id = id_stock_transfer.id
            ddi_id.pir_id.get_sop_integration(ddi_id.product_id, ddi_id.supply_warehouse_id)
            ddi_id.pir_id.get_sop_demand(ddi_id.product_id, ddi_id.supply_warehouse_id, ddi_id.origin, ddi_id.date_planned)
        id_stock_transfer.button_confirm()
        return True






