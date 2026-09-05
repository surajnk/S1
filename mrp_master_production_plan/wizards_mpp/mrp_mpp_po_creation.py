# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, time, timedelta
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


class MrpMppPOCreation(models.TransientModel):
    _name = 'mrp.mpp.po.creation'
    _description = "MPP Subcontracting PO Creation"


    def _default_mpp_ids(self):
        return self.env['mrp.production.plan'].browse(self.env.context.get('active_ids'))

    mpp_ids = fields.Many2many("mrp.production.plan", string='Master Production Plan Items', default=lambda self: self._default_mpp_ids())
    subcontractor_id = fields.Many2one('res.partner', 'Subcontractor')


    def _check_subcontractor(self):
        for mpp_id in self.mpp_ids:
            if mpp_id.subcontractor_id and mpp_id.subcontractor_id.name.id != self.subcontractor_id.id:
                raise UserError(_('Choosen subcontractor is different to the assigned ones'))
            if not mpp_id.subcontractor_id:
                subcontractor = self.env['product.supplierinfo'].search([('name','=', self.subcontractor_id.id),('product_tmpl_id','=', mpp_id.product_id.id),('is_subcontractor','=', True)], limit=1)
                if not subcontractor:
                    raise UserError(_('Supplierinfo has not been created for the product %s')% dpi_id.product_id.name)
                else:
                    mpp_id.subcontractor_id = subcontractor.id
        return True

    def _check_warehouse(self):
        warehouses = self.mpp_ids.mapped('warehouse_id')
        if len(warehouses) != 1:
            raise UserError(_('Warehouse is not the same for all selected items'))
        return True

    def _get_date_order(self):
        date_order = False
        delay_set = []
        date_planned_set = []
        company_set = []
        for mpp_id in self.mpp_ids:
            delay_set.append(mpp_id.subcontractor_id.delay)
            date_planned_set.append(mpp_id.date_planned)
        company_set = self.mpp_ids.mapped('company_id')
        purchase_lead_time = max(delay_set) + company_set[0].days_to_purchase
        date_order = min(date_planned_set) - timedelta(days=purchase_lead_time)
        return date_order

    def get_purchase_order(self):
        if any(mpp_id.state != 'draft' for mpp_id in self.mpp_ids):
            raise UserError(_('All selected items are to be in draft status'))
        if any(mpp_id.bom_id.type != 'subcontract'for mpp_id in self.mpp_ids):
            raise UserError(_('All selected items are to be subcontracting ones'))
        self._check_subcontractor()
        self._check_warehouse()
        date_order = self._get_date_order()
        warehouse_id = self.mpp_ids.mapped('warehouse_id')[0]
        id_purchase_order = self.env['purchase.order'].create({
            'partner_id': self.subcontractor_id.id,
            'currency_id': warehouse_id.company_id.currency_id.id,
            'company_id': warehouse_id.company_id.id,
            'origin': 'MPP: ' + datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'date_order': date_order,
            'user_id': self.env.user.id,
            'picking_type_id': warehouse_id.in_type_id.id,
        })
        for mpp_id in self.mpp_ids:
            subcontractor = self.env['product.supplierinfo'].search([('name','=', self.subcontractor_id.id),('product_tmpl_id','=', mpp_id.product_id.id),('is_subcontractor','=', True)], limit=1)
            id_purchase_order_item = self.env['purchase.order.line'].create({
                'order_id': id_purchase_order.id,
                'date_planned': mpp_id.date_planned,
                'product_id': mpp_id.product_id.id,
                'name': mpp_id.product_id.name,
                'product_uom': mpp_id.product_uom_id.id,
                'product_qty': mpp_id.product_qty,
                'price_unit': subcontractor.price,
                'mpp_id': mpp_id.id,
            })
            mpp_id.state = 'done'
        return True
