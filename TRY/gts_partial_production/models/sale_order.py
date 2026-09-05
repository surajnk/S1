# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # total_customer_qty = fields.Float("Delivered Qty", compute='_compute_customer_qty_delivered')
    #
    # @api.depends('move_ids.state', 'move_ids.scrapped', 'move_ids.product_uom_qty', 'move_ids.product_uom')
    # def _compute_customer_qty_delivered(self):
    #     for line in self:
    #         # if line.qty_delivered_method == 'stock_move':
    #             qty = 0.0
    #             outgoing_moves, incoming_moves = line._get_outgoing_incoming_moves()
    #             for move in outgoing_moves:
    #                 if move.state != 'done':
    #                     continue
    #                 qty += move.cust_qty
    #             for move in incoming_moves:
    #                 if move.state != 'done':
    #                     continue
    #                 qty -= move.cust_qty
    #             line.total_customer_qty = qty


    # @api.depends('move_ids.state', 'move_ids.scrapped', 'move_ids.product_uom_qty', 'move_ids.product_uom')
    # def _compute_qty_delivered(self):
    #     # super(SaleOrderLine, self)._compute_qty_delivered()
    #     print("\n\n\n -------------------- >>>>>> line >>>>>", line)
    #     for line in self:
    #         print ("\n\n\n -------------------- >>>>>> line >>>>>", line)
    #         # if line.qty_delivered_method == 'stock_move':
    #         qty = 0.0
    #         outgoing_moves, incoming_moves = line._get_outgoing_incoming_moves()
    #         for move in outgoing_moves:
    #             if move.state != 'done':
    #                 continue
    #             qty += move.cust_qty
    #         for move in incoming_moves:
    #             if move.state != 'done':
    #                 continue
    #             qty -= move.cust_qty
    #         line.qty_delivered = qty

    @api.depends('move_ids.state', 'move_ids.scrapped', 'move_ids.product_uom_qty', 'move_ids.product_uom')
    def _compute_qty_delivered(self):
        super(SaleOrderLine, self)._compute_qty_delivered()
        for line in self:  # TODO: maybe one day, this should be done in SQL for performance sake
            if line.qty_delivered_method == 'stock_move':
                qty = 0.0
                outgoing_moves, incoming_moves = line._get_outgoing_incoming_moves()
                for move in outgoing_moves:
                    if move.state != 'done':
                        continue
                    qty += move.cust_qty
                for move in incoming_moves:
                    if move.state != 'done':
                        continue
                    qty -= move.cust_qty
                line.qty_delivered = qty
