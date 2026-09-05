# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, time, timedelta
from odoo.exceptions import UserError


class MrpDistributionProcurement(models.Model):
    _name = "mrp.distribution.procurement"
    _description = "Distribution Procurement Items"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_planned'

    STATE_SELECTION = [
        ("draft", _("Draft")),
        ("cancel", _("Cancelled")),
        ("done", _("Approved"))]


    origin = fields.Many2one('mrp.planning.version', 'Version', readonly=True, related='pir_id.origin')
    user_id = fields.Many2one('res.users', 'Planning Responsible', related='pir_id.user_id', store=True)
    active = fields.Boolean(default=True)
    date_planned = fields.Datetime('Planned Date', readonly=True)
    date_order = fields.Datetime('Order Date', readonly=True)
    state = fields.Selection(STATE_SELECTION, 'State', required=True, readonly=True, default='draft')
    product_id = fields.Many2one("product.product", 'Product', required=True, readonly=True, check_company=True, domain=[('type', 'in', ['product', 'consu'])])
    product_qty = fields.Float("Planned Qty", required=True, digits='Product Unit of Measure', readonly=True, default='1')
    product_uom_id = fields.Many2one('uom.uom', 'UoM', readonly=True, related='product_id.uom_id', store=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', related='product_id.product_tmpl_id')
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse' , required=True, readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True, related='warehouse_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', related='warehouse_id.company_id.currency_id')
    pir_id = fields.Many2one('mrp.independent.requirements', 'PIR ID', readonly=True)
    purchase_id = fields.Many2one('purchase.order', 'Purchase Order', readonly=True)
    purchase_state = fields.Selection(string='Purchase Order State', related='purchase_id.state')
    supplier_id = fields.Many2one('product.supplierinfo', 'Supplier', readonly=True, states={'draft': [('readonly', False)]})


    def _get_order_date(self):
        date_order = False
        for record in self:
            days_to_purchase = record.company_id.days_to_purchase
            supplier_delay = record.supplier_id.delay
            purchase_lead_time = supplier_delay + days_to_purchase
            date_order = record.date_planned - timedelta(days=purchase_lead_time)
            if record.warehouse_id.calendar_id and not days_to_purchase == 0:
                calendar = record.warehouse_id.calendar_id
                date_order = record.date_planned - timedelta(days=supplier_delay)
                date_order = calendar.plan_days(-days_to_purchase - 1, date_order, True)
        return date_order

    def action_purchase_order_create(self):
        self.ensure_one()
        date_order = self._get_order_date()
        id_purchase_order = self.env['purchase.order'].create({
            'partner_id': self.supplier_id.name.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'origin': 'DRP: ' + self.pir_id.origin.name,
            'date_order': date_order,
            'user_id': self.pir_id.origin.user_id.id,
            'picking_type_id': self.warehouse_id.in_type_id.id,
        })
        id_purchase_order_item = self.env['purchase.order.line'].create({
            'order_id': id_purchase_order.id,
            'date_planned': self.date_planned,
            'product_id': self.product_id.id,
            'name': self.product_id.name,
            'product_uom': self.product_uom_id.id,
            'product_qty': self.product_qty,
            'price_unit': self.supplier_id.price,
            'pir_id': self.pir_id.id,
        })
        self.purchase_id = id_purchase_order.id
        self.date_order = date_order
        return True

    def button_done(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(_('Approval is possible in draft status only'))
        for record in self:
            if not record.supplier_id:
                raise UserError(_('no supplier has been entered'))
            record.state = 'done'
            record.action_purchase_order_create()
            record.pir_id.purchase_id = record.purchase_id.id
        return True

    def unlink(self):
        if any(record.state != 'cancel' for record in self):
            raise UserError(_('Deletion is possible in cancel status only'))
        return super().unlink()
