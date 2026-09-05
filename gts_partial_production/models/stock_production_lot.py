# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductionLot(models.Model):
    _inherit = 'stock.production.lot'
    _order = 'create_date desc'

    @api.depends('quant_ids')
    def _has_quants(self):
        for lot in self:
            if lot.quant_ids:
                lot.has_quants = True
            else:
                lot.has_quants = False

    has_quants = fields.Boolean('Has Quants?', compute='_has_quants', store=True)
    quantity_done = fields.Float('Done', default=1.0)
    customer_qty = fields.Float("Customer Qty")


# class StockLots(models.Model):
#     _inherit = 'stock.production.lot'
#

    # _sql_constraints = [
    #     ('uniq_lot_id', 'unique(move_id, lot_id)', 'You have already mentioned this lot in another line')]


class Inventory(models.Model):
    _inherit = "stock.inventory"
    _order = 'date desc'


# class StockPicking(models.Model):
#     _inherit = 'stock.picking'
#     _order = 'min_date desc'
