# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, time, timedelta
from odoo.exceptions import UserError


class MrpDistributionDeployment(models.Model):
    _name = "mrp.distribution.deployment"
    _description = "Distribution Deployment Items"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_planned'

    STATE_SELECTION = [
        ("draft", _("Draft")),
        ("cancel", _("Cancelled")),
        ("done", _("Approved"))]


    origin = fields.Many2one('mrp.planning.version', 'Version', readonly=True, related='pir_id.origin')
    user_id = fields.Many2one('res.users', 'Planning Responsible', related='pir_id.user_id', store=True)
    active = fields.Boolean(default=True)
    date = fields.Datetime('Stock Transfer Document Date', readonly=True)
    date_planned = fields.Datetime('Planned Date', readonly=True, states={'draft': [('readonly', False)]})
    state = fields.Selection(STATE_SELECTION, 'State', required=True, copy=False, default='draft')
    product_id = fields.Many2one("product.product", 'Product', required=True, check_company=True, domain=[('type', 'in', ['product', 'consu'])],
        readonly=True, states={'draft': [('readonly', False)]})
    product_qty = fields.Float("Planned Qty", required=True, digits='Product Unit of Measure',
        readonly=True, states={'draft': [('readonly', False)]}, default='1')
    product_uom_id = fields.Many2one('uom.uom', 'UoM', readonly=True, related='product_id.uom_id', store=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', required=True, readonly=True, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one('res.company', 'Company', readonly=True, related='supply_warehouse_id.company_id', store=True)
    supply_warehouse_id = fields.Many2one('stock.warehouse', required=True, readonly=True, states={'draft': [('readonly', False)]})
    pir_id = fields.Many2one('mrp.independent.requirements', 'PIR ID', readonly=True)
    stock_transfer_id = fields.Many2one('stock.transfer', 'Stock Transfer Document', readonly=True)
    stock_transfer_state = fields.Selection(string=_('Stock Transfer State'), related='stock_transfer_id.state')


    def action_stock_transfer_document_create(self):
        for record in self:
            days_to_purchase = record.warehouse_id.company_id.days_to_purchase
            date = record.date_planned - timedelta(days=days_to_purchase)
            if record.warehouse_id.calendar_id and not days_to_purchase == 0:
                calendar = record.warehouse_id.calendar_id
                date = calendar.plan_days(-days_to_purchase - 1, record.date_planned, True)
            id_stock_transfer = self.env['stock.transfer'].create({
                'company_id': record.company_id.id,
                'origin': 'DRP: ' + record.pir_id.origin.name,
                'user_id': record.pir_id.origin.user_id.id,
                'warehouse_id': record.warehouse_id.id,
                'source_warehouse_id': record.supply_warehouse_id.id,
                'date_planned': record.date_planned,
                'date': date,
            })
            id_stock_transfer_line = self.env['stock.transfer.line'].create({
                'stock_transfer_id': id_stock_transfer.id,
                'product_id': record.product_id.id,
                'name': record.product_id.name,
                'product_uom': record.product_uom_id.id,
                'product_qty': record.product_qty,
                'pir_id': record.pir_id.id,
            })
            record.stock_transfer_id = id_stock_transfer.id
            record.date = date
        return True

    def button_done(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(_('Approval is possible in draft status only'))
        for record in self:
            record.action_stock_transfer_document_create()
            record.stock_transfer_id.button_confirm()
            record.pir_id.get_sop_integration(record.product_id, record.supply_warehouse_id)
            record.pir_id.get_sop_demand(record.product_id, record.supply_warehouse_id, record.origin, record.date_planned)
            record.pir_id.stock_transfer_id = record.stock_transfer_id.id
            record.state = 'done'
        return True

    def unlink(self):
        if any(record.state != 'cancel' for record in self):
            raise UserError(_('Deletion is possible in cancel status only'))
        return super().unlink()
