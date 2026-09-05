# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, time, timedelta
from odoo.exceptions import UserError


class MrpDpiPOCreation(models.TransientModel):
    _name = 'mrp.dpi.po.creation'
    _description = "Distribution Procurement PO Creation"


    def _default_dpi_ids(self):
        return self.env['mrp.distribution.procurement'].browse(self.env.context.get('active_ids'))

    dpi_ids = fields.Many2many("mrp.distribution.procurement", string='Distribution Procurement Items', default=lambda self: self._default_dpi_ids())
    vendor_id = fields.Many2one('res.partner', 'Supplier')


    def _check_supplier(self):
        for dpi_id in self.dpi_ids:
            if dpi_id.supplier_id and dpi_id.supplier_id.name.id != self.vendor_id.id:
                raise UserError(_('Choosen supplier is different to the assigned ones'))
            if not dpi_id.supplier_id:
                supplier = self.env['product.supplierinfo'].search([('name','=', self.vendor_id.id),('product_tmpl_id','=', dpi_id.product_id.id),('is_subcontractor','=', False)], limit=1)
                if not supplier:
                    raise UserError(_('Supplierinfo has not been created for the product %s')% dpi_id.product_id.name)
                else:
                    dpi_id.supplier_id = supplier.id
        return True

    def _check_warehouse(self):
        warehouses = self.dpi_ids.mapped('warehouse_id')
        if len(warehouses) != 1:
            raise UserError(_('Warehouse is not the same for all selected items'))
        return True

    def _check_version(self):
        versions = self.dpi_ids.mapped('origin')
        if len(versions) != 1:
            raise UserError(_('Version is not the same for all selected items'))
        return True

    def _get_date_order(self):
        date_order = False
        delay_set = []
        date_planned_set = []
        company_set = []
        for dpi_id in self.dpi_ids:
            delay_set.append(dpi_id.supplier_id.delay)
            date_planned_set.append(dpi_id.date_planned)
        company_set = self.dpi_ids.mapped('company_id')
        purchase_lead_time = max(delay_set) + company_set[0].days_to_purchase
        date_order = min(date_planned_set) - timedelta(days=purchase_lead_time)
        return date_order

    def get_purchase_order(self):
        if any(dpi_id.state != 'draft' for dpi_id in self.dpi_ids):
            raise UserError(_('All selected items are to be in draft status'))
        self._check_supplier()
        self._check_warehouse()
        self._check_version()
        warehouse_id = self.dpi_ids.mapped('warehouse_id')[0]
        first_pir_id = self.dpi_ids.mapped('pir_id')[0]
        date_order = self._get_date_order()
        id_purchase_order = self.env['purchase.order'].create({
            'partner_id': self.vendor_id.id,
            'currency_id': first_pir_id.currency_id.id,
            'company_id': first_pir_id.company_id.id,
            'origin': 'DRP: ' + first_pir_id.origin.name,
            'date_order': date_order,
            'user_id': first_pir_id.origin.user_id.id,
            'picking_type_id': warehouse_id.in_type_id.id,
        })
        for dpi_id in self.dpi_ids:
            supplier = self.env['product.supplierinfo'].search([('name','=', self.vendor_id.id),('product_tmpl_id','=', dpi_id.product_id.id),('is_subcontractor','=', False)], limit=1)
            id_purchase_order_item = self.env['purchase.order.line'].create({
                'order_id': id_purchase_order.id,
                'date_planned': dpi_id.date_planned,
                'product_id': dpi_id.product_id.id,
                'name': dpi_id.product_id.name,
                'product_uom': dpi_id.product_uom_id.id,
                'product_qty': dpi_id.product_qty,
                'price_unit': supplier.price,
                'pir_id': dpi_id.pir_id.id,
            })
            dpi_id.state = 'done'
            dpi_id.date_order = date_order
            dpi_id.pir_id.purchase_id = id_purchase_order.id
            dpi_id.purchase_id = id_purchase_order.id
        return True
