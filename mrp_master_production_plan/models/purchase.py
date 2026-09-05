# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"


    pir_id = fields.Many2one('mrp.independent.requirements', string='PIR ID', readonly=True)
    mpp_id = fields.Many2one('mrp.production.plan', 'MPP ID')


class StockTransferLine(models.Model):
    _inherit = "stock.transfer.line"


    pir_id = fields.Many2one('mrp.independent.requirements', string='PIR ID', readonly=True)

