# -*- coding: utf-8 -*-
import logging
import math

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    cust_qty = fields.Float("Customer Qty", compute="compute_cust_qty")

    def compute_cust_qty(self):
        for rec in self:
            total_cust_qty = 0
            for line in rec.move_line_ids:
                total_cust_qty += line.customer_qty
            rec.cust_qty = total_cust_qty


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    customer_qty = fields.Float("Customer Qty")

    x_customer_uom_id = fields.Many2one(
        'uom.uom', string='Customer UOM', compute='_compute_x_customer_uom_id')

    @api.depends('move_id', 'move_id.sale_line_id', 'move_id.group_id',
                 'move_id.group_id.sale_id', 'move_id.production_id',
                 'product_id')
    def _compute_x_customer_uom_id(self):
        for line in self:
            sale_line = line._get_sale_line_for_uom()
            line.x_customer_uom_id = sale_line.x_order_customer_uom if sale_line else False

    def _get_sale_line_for_uom(self):
        self.ensure_one()
        move = self.move_id
        if not move:
            return self.env['sale.order.line']
        if move.sale_line_id:
            return move.sale_line_id
        sale_order = move.group_id.sale_id
        if not sale_order and move.production_id:
            sale_order = move.production_id.procurement_group_id.sale_id
        if not sale_order:
            production = move.production_id or move.move_orig_ids.mapped('production_id')[:1]
            if production:
                sale_order = production.procurement_group_id.sale_id
        if not sale_order:
            return self.env['sale.order.line']
        sale_line = sale_order.order_line.filtered(
            lambda l: l.product_id.id == self.product_id.id)[:1]
        return sale_line

    @api.model_create_multi
    def create(self, vals_list):
        """When a new move line is created with a lot_id that already
        has customer_qty stamped on it (set by the production wizard),
        automatically populate the line's own customer_qty from the lot.

        This handles the skip_split path where delivery lines are created
        after the lot is stamped, not during re_generate_putup_move_line().
        """
        records = super().create(vals_list)
        for record in records:
            if record.lot_id and record.lot_id.customer_qty and not record.customer_qty:
                record.customer_qty = record.lot_id.customer_qty
        return records

    def open_on_hand_qtystock(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Quantity',
            'view_mode': 'tree,form',
            'res_model': 'stock.quant',
            'domain': [['product_id', '=', self.product_id.id]],
            'context': {'default_product_id': self.product_id.id},
            'target': 'new'
        }

    def _get_production_for_inverse(self):
        self.ensure_one()
        move = self.move_id
        if move:
            production = (
                move.production_id
                or move.move_orig_ids.mapped('production_id')[:1]
            )
            if production:
                return production

        # move_id may be empty in inline tree onchange context -
        # fall back to finding production via the lot directly
        if self.lot_id:
            prod_move_line = self.env['stock.move.line'].search([
                ('lot_id', '=', self.lot_id.id),
                ('move_id.production_id', '!=', False),
            ], limit=1)
            if prod_move_line:
                return prod_move_line.move_id.production_id

        return self.env['mrp.production']

    # def _get_production_for_inverse(self):
    #     self.ensure_one()
    #     move = self.move_id
    #     if not move:
    #         return self.env['mrp.production']
    #     production = (
    #         move.production_id
    #         or move.move_orig_ids.mapped('production_id')[:1]
    #     )
    #     if production:
    #         return production
    #     if self.lot_id:
    #         prod_move_line = self.env['stock.move.line'].search([
    #             ('lot_id', '=', self.lot_id.id),
    #             ('move_id.production_id', '!=', False),
    #         ], limit=1)
    #         if prod_move_line:
    #             return prod_move_line.move_id.production_id
    #     return self.env['mrp.production']

    def _compute_yards_from_customer_qty(self, customer_qty, production):
        if not customer_qty or not production:
            return 0.0
        if not production.origin:
            return customer_qty
        customer_width = production.x_order_line_customer_mrp_width or 1
        customer_length = production.x_order_line_customer_mrp_length or '0.0'
        trim_width = production.x_order_line_trim_width
        trim_length = production.x_order_line_trim_length
        machine_length = production.x_order_line_machine_length or 41
        component_width = (
            production.move_raw_ids
            and production.move_raw_ids[0].product_id.x_item_width
            or 1
        )
        if customer_width == component_width:
            trim_width = 0
            width_outs = (int(component_width - trim_width) / customer_width) or 1
            width_outs_final = math.trunc(math.modf(width_outs)[1])
            master_yards = int(customer_qty) / width_outs_final
            if not float(master_yards).is_integer():
                master_yards = int(master_yards) + 1
            return float(master_yards)
        if customer_width != component_width and customer_length == '0.0':
            width_outs = int((component_width - trim_width) / customer_width) or 1
            width_outs_final = math.trunc(math.modf(width_outs)[1])
            master_yards = int(customer_qty) / width_outs_final
            if not float(master_yards).is_integer():
                master_yards = int(master_yards) + 1
            return float(master_yards)
        width_outs = int((component_width - trim_width) / customer_width)
        width_outs_final = math.trunc(math.modf(width_outs)[1])
        counter = 1
        length_outs = (counter * customer_length) + trim_length
        length_outs_final = math.trunc(math.modf(length_outs)[1])
        while length_outs_final < machine_length:
            counter += 1
            length_outs_final = math.trunc(
                math.modf((counter * customer_length) + trim_length)[1])
        length_outs_final = counter - 1
        master_sheet_length = (length_outs_final * customer_length) + trim_length
        machine_stops = self.env['machine.stops'].search([
            ('x_machine_st', '>=', master_sheet_length)], limit=1)
        if machine_stops:
            master_sheet_length = machine_stops.x_machine_st
        master_outs = (width_outs_final * length_outs_final) or 1
        master_sheets = int(customer_qty) / master_outs
        if not float(master_sheets).is_integer():
            master_sheets = int(master_sheets) + 1
        master_yards = int(master_sheets * master_sheet_length) / 36
        if not float(master_yards).is_integer():
            master_yards = int(master_yards) + 1
        return float(master_yards)

    @api.onchange('customer_qty')
    def _onchange_customer_qty_set_qty_done(self):
        for line in self:
            _logger.info(
                "[GTS onchange] fired: line.id=%s customer_qty=%s move_id=%s lot_id=%s",
                line.id, line.customer_qty,
                line.move_id.id if line.move_id else None,
                line.lot_id.id if line.lot_id else None,
            )
            if not line.customer_qty:
                continue

            if line.lot_id:
                line.lot_id.customer_qty = line.customer_qty

            if line.move_id:
                move_production_id = line.move_id.production_id
                if move_production_id:
                    _logger.info("[GTS onchange] skipping - production line")
                    continue

            production = line._get_production_for_inverse()
            if not production:
                _logger.info(
                    "[GTS onchange] no production found for line.id=%s lot_id=%s",
                    line.id, line.lot_id.id if line.lot_id else None,
                )
                continue

            yards = line._compute_yards_from_customer_qty(line.customer_qty, production)
            _logger.info(
                "[GTS onchange] line.id=%s customer_qty=%s -> yards=%s",
                line.id, line.customer_qty, yards,
            )
            line.qty_done = yards

#====================================================================================


# # -*- coding: utf-8 -*-
# import logging

# from odoo import api, fields, models, _
# import math

# _logger = logging.getLogger(__name__)


# class StockMove(models.Model):
#     _inherit = 'stock.move'

#     cust_qty = fields.Float("Customer Qty", compute="compute_cust_qty")

#     def compute_cust_qty(self):
#         for rec in self:
#             total_cust_qty = 0
#             for line in rec.move_line_ids:
#                 total_cust_qty += line.customer_qty
#             rec.cust_qty = total_cust_qty


# class StockMoveLine(models.Model):
#     _inherit = 'stock.move.line'
    
#     customer_qty = fields.Float("Customer Qty")
#     x_customer_uom_id = fields.Many2one(
#         'uom.uom', string='Customer UOM', compute='_compute_x_customer_uom_id')

#     @api.depends('move_id', 'move_id.sale_line_id', 'move_id.group_id',
#                  'move_id.group_id.sale_id', 'move_id.production_id',
#                  'product_id')
#     def _compute_x_customer_uom_id(self):
#         for line in self:
#             sale_line = line._get_sale_line_for_uom()
#             _logger.info(
#                 "[GTS DEBUG UOM] line.id=%s move_id=%s sale_line_id=%s sale_line.x_order_customer_uom=%s",
#                 line.id,
#                 line.move_id.id if line.move_id else None,
#                 sale_line.id if sale_line else None,
#                 sale_line.x_order_customer_uom.name if sale_line and sale_line.x_order_customer_uom else None,
#             )
#             line.x_customer_uom_id = sale_line.x_order_customer_uom if sale_line else False

#     def _get_sale_line_for_uom(self):
#         self.ensure_one()
#         move = self.move_id
#         if not move:
#             return self.env['sale.order.line']

#         if move.sale_line_id:
#             return move.sale_line_id

#         sale_order = move.group_id.sale_id
#         if not sale_order and move.production_id:
#             sale_order = move.production_id.procurement_group_id.sale_id
#         if not sale_order:
#             production = move.production_id or move.move_orig_ids.mapped('production_id')[:1]
#             if production:
#                 sale_order = production.procurement_group_id.sale_id

#         _logger.info(
#             "[GTS DEBUG UOM TRACE] line.id=%s move.id=%s group_id.sale_id=%s "
#             "resolved sale_order=%s product_id=%s",
#             self.id, move.id,
#             move.group_id.sale_id.id if move.group_id and move.group_id.sale_id else None,
#             sale_order.id if sale_order else None,
#             self.product_id.id if self.product_id else None,
#         )

#         if not sale_order:
#             return self.env['sale.order.line']

#         sale_line = sale_order.order_line.filtered(
#             lambda l: l.product_id.id == self.product_id.id)[:1]
#         return sale_line

#     def open_on_hand_qtystock(self):
#         """
#         """
#         return {
#             'type': 'ir.actions.act_window',
#             'name': 'Product Quantity',
#             'view_mode': 'tree,form',
#             'res_model': 'stock.quant',
#             'domain': [['product_id', '=', self.product_id.id]],
#             'context': {'default_product_id': self.product_id.id},
#             'target': 'new'
#         }

#     def _get_previous_chain_line(self):
#         self.ensure_one()
#         _logger.info(
#             "[GTS DEBUG] _get_previous_chain_line: self.id=%s lot_id=%s picking_id=%s",
#             self.id, self.lot_id.id if self.lot_id else None,
#             self.picking_id.id if self.picking_id else None,
#         )
#         if not self.lot_id:
#             _logger.info("[GTS DEBUG] _get_previous_chain_line: no lot_id on this line, returning empty")
#             return self.env['stock.move.line']
#         domain = [('lot_id', '=', self.lot_id.id), ('customer_qty', '!=', 0)]
#         if self.picking_id and isinstance(self.picking_id.id, int):
#             domain.append(('picking_id', '!=', self.picking_id.id))
#         _logger.info("[GTS DEBUG] _get_previous_chain_line: search domain=%s", domain)
#         previous_line = self.search(domain, order='date desc, id desc', limit=1)
#         _logger.info(
#             "[GTS DEBUG] _get_previous_chain_line: found previous_line.id=%s qty_done=%s "
#             "customer_qty=%s picking=%s",
#             previous_line.id if previous_line else None,
#             previous_line.qty_done if previous_line else None,
#             previous_line.customer_qty if previous_line else None,
#             previous_line.picking_id.name if previous_line and previous_line.picking_id else None,
#         )
#         return previous_line

#     @api.onchange('qty_done')
#     def _onchange_qty_done_set_customer_qty(self):
#         for line in self:
#             _logger.info(
#                 "[GTS DEBUG] ===== onchange fired: line.id=%s qty_done=%s move_id=%s lot_id=%s picking=%s",
#                 line.id, line.qty_done,
#                 line.move_id.id if line.move_id else None,
#                 line.lot_id.id if line.lot_id else None,
#                 line.picking_id.name if line.picking_id else None,
#             )

#             if not line.qty_done or not line.move_id:
#                 _logger.info("[GTS DEBUG] no qty_done or no move_id -> setting customer_qty=0")
#                 line.customer_qty = 0
#                 continue

#             move_production_id = line.move_id.production_id
#             move_orig_production = line.move_id.move_orig_ids.mapped('production_id')[:1]
#             _logger.info(
#                 "[GTS DEBUG] move_id.production_id=%s | move_orig_ids.production_id=%s",
#                 move_production_id.id if move_production_id else None,
#                 move_orig_production.id if move_orig_production else None,
#             )

#             production = move_production_id or move_orig_production

#             if production:
#                 _logger.info("[GTS DEBUG] PRODUCTION BRANCH: production.id=%s", production.id)
#                 customer_qty = production._compute_customer_qty_from_yards(line.qty_done)
#                 _logger.info("[GTS DEBUG] PRODUCTION BRANCH: computed customer_qty=%s", customer_qty)
#                 line.customer_qty = customer_qty
#                 if line.lot_id:
#                     line.lot_id.customer_qty = customer_qty
#                 continue

#             _logger.info("[GTS DEBUG] DELIVERY BRANCH: no production resolved on this move, tracing back chain")

#             previous_line = line._get_previous_chain_line()
#             if not previous_line or not previous_line.qty_done:
#                 _logger.info(
#                     "[GTS DEBUG] DELIVERY BRANCH: no usable previous_line found "
#                     "(previous_line=%s, qty_done=%s) -> leaving customer_qty unchanged",
#                     bool(previous_line),
#                     previous_line.qty_done if previous_line else None,
#                 )
#                 continue

#             full_customer_qty = previous_line.customer_qty
#             ratio = line.qty_done / previous_line.qty_done
#             _logger.info(
#                 "[GTS DEBUG] DELIVERY BRANCH: previous_line.customer_qty=%s "
#                 "previous_line.qty_done=%s this_line.qty_done=%s ratio=%s -> final customer_qty=%s",
#                 full_customer_qty, previous_line.qty_done,
#                 line.qty_done, ratio, full_customer_qty * ratio,
#             )
#             line.customer_qty = full_customer_qty * ratio
