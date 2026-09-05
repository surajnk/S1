# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import math


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

    customer_qty = fields.Float("Customer Qty", related='lot_id.customer_qty')

    def open_on_hand_qtystock(self):
        """
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Quantity',
            'view_mode': 'tree,form',
            'res_model': 'stock.quant',
            'domain': [['product_id', '=', self.product_id.id]],
            'context': {'default_product_id': self.product_id.id},
            'target': 'new'
        }

    @api.onchange('qty_done')
    def _onchange_qty_done_set_customer_qty(self):
        """Update customer quantity based on the yards (qty_done)."""
        for line in self:
            if not line.qty_done or not line.move_id:
                if line.lot_id:
                    line.lot_id.customer_qty = 0
                continue

            production = line.move_id.production_id or \
                line.move_id.move_orig_ids.mapped('production_id')[:1]
            if not production:
                continue

            if not production.origin:
                customer_qty = line.qty_done
            else:
                yards = line.qty_done
                customer_width = production.x_order_line_customer_mrp_width or 1
                customer_length = production.x_order_line_customer_mrp_length or '0.0'
                trim_width = production.x_order_line_trim_width
                trim_length = production.x_order_line_trim_length
                machine_length = production.x_order_line_machine_length or 41
                component_width = production.move_raw_ids and production.move_raw_ids[0].product_id.x_item_width or 1

                if customer_width == component_width:
                    trim_width = 0
                    width_outs = (int(component_width - trim_width) / customer_width) or 1
                    width_outs_final = math.trunc(math.modf(width_outs)[1])
                    customer_qty = yards * width_outs_final
                elif customer_width != component_width and customer_length == '0.0':
                    width_outs = int((component_width - trim_width) / customer_width) or 1
                    width_outs_final = math.trunc(math.modf(width_outs)[1])
                    customer_qty = yards * width_outs_final
                else:
                    width_outs = int((component_width - trim_width) / customer_width)
                    width_outs_final = math.trunc(math.modf(width_outs)[1])
                    counter = 1
                    length_outs = (counter * customer_length) + trim_length
                    length_outs_final = math.trunc(math.modf(length_outs)[1])
                    while length_outs_final < machine_length:
                        counter += 1
                        length_outs_final = math.trunc(math.modf((counter * customer_length) + trim_length)[1])
                    length_outs_final = counter - 1
                    master_sheet_length = (length_outs_final * customer_length) + trim_length
                    machine_stops = self.env['machine.stops'].search([
                        ('x_machine_st', '>=', master_sheet_length)], limit=1)
                    master_sheet_length = machine_stops.x_machine_st
                    master_outs = (width_outs_final * length_outs_final) or 1
                    master_sheets = math.ceil((yards * 36) / master_sheet_length)
                    customer_qty = master_sheets * master_outs

            if line.lot_id:
                line.lot_id.customer_qty = customer_qty
