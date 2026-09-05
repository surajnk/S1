from itertools import chain
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_repr
from odoo.tools.misc import get_lang
from decimal import Decimal, ROUND_HALF_UP
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.depends('x_order_line_bom', 'x_order_line_bom.x_product_bom_select', 'x_order_line_bom.x_unit_req','x_order_master_yards', 'product_id',)
    def _compute_master_yards(self):
        res = super(SaleOrderLine, self)._compute_master_yards()
        a = disc_price = 0
        val_flag = False
        price_string = ''
        for item_line in self.order_id.pricelist_id.item_ids:
            # _logger.info('item_line filter %s',item_line.filtered(lambda x:x.product_tmpl_id.id == self.product_id.product_tmpl_id.id))
            if self.x_order_master_yards > 0 and self.order_id.pricelist_id and item_line.applied_on == '1_product' and item_line.filtered(
                    lambda x: x.product_tmpl_id.id == self.product_id.product_tmpl_id.id) and (
                    self.order_id.partner_id.x_special_pricing or self.order_id.partner_id.parent_id.x_special_pricing):
                if item_line.use_cust_units == 'master_yards':
                    for qty_breaks in item_line.x_pricelist_break_qty_price:
                        split_values = qty_breaks.x_product_qty_pr.split('-')
                        if self.x_order_master_yards >= float(split_values[0]) and self.x_order_master_yards <= float(
                                split_values[1]):
                            if (
                                    int(qty_breaks.x_product_lvl_pr) > 0 and qty_breaks.x_product_price_per_value_pr == 0.00000):
                                a = int(qty_breaks.x_product_lvl_pr)
                                if a > 0:
                                    pricelist_lines = self.env['product.quantity.pricelist'].sudo().search(
                                        [('product_pricelist_item_id', '=', item_line.id)], limit=a)
                                    if pricelist_lines:
                                        disc_price = (pricelist_lines[-1].x_product_level_price_pr * pricelist_lines[
                                            -1].x_product_discount_on_level_pr) / 100
                                        self.price_unit = round(
                                            pricelist_lines[-1].x_product_level_price_pr - disc_price, 5)
                                        val_flag = True
                                        price_string = ('''Unit price has been fetched from Pricelist rule:''',
                                                        item_line.name)
                                        _logger.info('pricelist lines for unit price inside product %s',
                                                     self.price_unit)
                            else:
                                self.price_unit = Decimal(qty_breaks.x_product_price_per_value_pr).quantize(
                                    Decimal('0.00001'), rounding=ROUND_HALF_UP)
                                val_flag = True
                else:
                    for qty_breaks in item_line.x_pricelist_break_cust_qty_price:
                        split_values = qty_breaks.x_product_cust_qty_pr.split('-')
                        if self.product_uom_qty >= float(split_values[0]) and self.product_uom_qty <= float(
                                split_values[1]):
                            self.customer_unit_price = Decimal(qty_breaks.x_product_cust_unit_price).quantize(
                                Decimal('0.00001'), rounding=ROUND_HALF_UP)
                            val_flag = True
                            price_string = ('''Unit price has been fetched from Custom Pricelist rule:''',
                                            item_line.name)
                            _logger.info('pricelist lines for custom unit price %s', self.price_unit)
                            break

            if self.x_order_master_yards > 0 and self.order_id.pricelist_id and item_line.applied_on == '4_item_group' and item_line.product_item_group_id.id == self.x_sale_line_item_group.id and (
                    self.order_id.partner_id.x_special_pricing or self.order_id.partner_id.parent_id.x_special_pricing):
                if item_line.use_cust_units == 'master_yards':
                    for qty_breaks in item_line.x_pricelist_break_qty_price:
                        split_values = qty_breaks.x_product_qty_pr.split('-')
                        if self.x_order_master_yards >= float(split_values[0]) and self.x_order_master_yards <= float(
                                split_values[1]):
                            if (
                                    int(qty_breaks.x_product_lvl_pr) > 0 and qty_breaks.x_product_price_per_value_pr == 0.00000):
                                a = int(qty_breaks.x_product_lvl_pr)
                                if a > 0:
                                    pricelist_lines = self.env['product.quantity.pricelist'].sudo().search(
                                        [('product_pricelist_item_id', '=', item_line.id)], limit=a)
                                    if pricelist_lines:
                                        disc_price = (pricelist_lines[-1].x_product_level_price_pr * pricelist_lines[
                                            -1].x_product_discount_on_level_pr) / 100
                                        self.price_unit = pricelist_lines[-1].x_product_level_price_pr - disc_price
                                        val_flag = True
                                        price_string = ('''Unit price has been fetched from Pricelist rule:''',
                                                        item_line.name)
                                        _logger.info('pricelist lines for unit price inside product %s', self.price_unit)
                                    # (qty_breaks.x_product_price_per_value_pr*qty_breaks.x_product_discount_on_level_pr)/100
                            else:
                                self.price_unit = qty_breaks.x_product_price_per_value_pr
                                val_flag = True
                else:
                    for qty_breaks in item_line.x_pricelist_break_cust_qty_price:
                        split_values = qty_breaks.x_product_cust_qty_pr.split('-')
                        if self.product_uom_qty >= float(split_values[0]) and self.product_uom_qty <= float(
                                split_values[1]):
                            self.customer_unit_price = Decimal(qty_breaks.x_product_cust_unit_price).quantize(
                                Decimal('0.00001'), rounding=ROUND_HALF_UP)
                            val_flag = True
                            price_string = ('''Unit price has been fetched from Custom Pricelist rule:''',
                                            item_line.name)
                            _logger.info('pricelist lines for custom unit price %s', self.price_unit)
                            break

            if self.x_order_master_yards > 0 and self.order_id.pricelist_id and item_line.applied_on == '6_price_group' and item_line.price_group_id.id == self.product_id.product_tmpl_id.x_product_price_group.id and (
                    self.order_id.partner_id.x_special_pricing or self.order_id.partner_id.parent_id.x_special_pricing):
                if item_line.use_cust_units == 'master_yards':
                    for qty_breaks in item_line.x_pricelist_break_qty_price:
                        split_values = qty_breaks.x_product_qty_pr.split('-')
                        if self.x_order_master_yards >= float(split_values[0]) and self.x_order_master_yards <= float(
                                split_values[1]):
                            if (
                                    int(qty_breaks.x_product_lvl_pr) > 0 and qty_breaks.x_product_price_per_value_pr == 0.00000):
                                a = int(qty_breaks.x_product_lvl_pr)
                                if a > 0:
                                    pricelist_lines = self.env['product.quantity.pricelist'].sudo().search(
                                        [('product_pricelist_item_id', '=', item_line.id)], limit=a)
                                    if pricelist_lines:
                                        disc_price = (pricelist_lines[-1].x_product_level_price_pr * pricelist_lines[
                                            -1].x_product_discount_on_level_pr) / 100
                                        self.price_unit = pricelist_lines[-1].x_product_level_price_pr - disc_price
                                        price_string = ('''Unit price has been fetched from Pricelist rule:''',
                                                        item_line.name)
                                        val_flag = True
                                    # (qty_breaks.x_product_price_per_value_pr*qty_breaks.x_product_discount_on_level_pr)/100
                            else:
                                self.price_unit = qty_breaks.x_product_price_per_value_pr
                                val_flag = True
                else:
                    for qty_breaks in item_line.x_pricelist_break_cust_qty_price:
                        split_values = qty_breaks.x_product_cust_qty_pr.split('-')
                        if self.product_uom_qty >= float(split_values[0]) and self.product_uom_qty <= float(
                                split_values[1]):
                            self.customer_unit_price = Decimal(qty_breaks.x_product_cust_unit_price).quantize(
                                Decimal('0.00001'), rounding=ROUND_HALF_UP)
                            val_flag = True
                            price_string = ('''Unit price has been fetched from Custom Pricelist rule:''',
                                            item_line.name)
                            _logger.info('pricelist lines for custom unit price %s', self.price_unit)
                            break

            if self.x_order_master_yards > 0 and self.order_id.pricelist_id and item_line.applied_on == '7_commodity_group' and item_line.product_commodity_id.id == self.x_sale_line_item_group.x_commodity_class.id and (
                    self.order_id.partner_id.x_special_pricing or self.order_id.partner_id.parent_id.x_special_pricing):
                if item_line.use_cust_units == 'master_yards':
                    for qty_breaks in item_line.x_pricelist_break_qty_price:
                        split_values = qty_breaks.x_product_qty_pr.split('-')
                        if self.x_order_master_yards >= float(split_values[0]) and self.x_order_master_yards <= float(
                                split_values[1]):
                            if (
                                    int(qty_breaks.x_product_lvl_pr) > 0 and qty_breaks.x_product_price_per_value_pr == 0.00000):
                                a = int(qty_breaks.x_product_lvl_pr)
                                if a > 0:
                                    pricelist_lines = self.env['product.quantity.pricelist'].sudo().search(
                                        [('product_pricelist_item_id', '=', item_line.id)], limit=a)
                                    if pricelist_lines:
                                        disc_price = (pricelist_lines[-1].x_product_level_price_pr * pricelist_lines[
                                            -1].x_product_discount_on_level_pr) / 100
                                        self.price_unit = pricelist_lines[-1].x_product_level_price_pr - disc_price
                                        price_string = ('''Unit price has been fetched from Pricelist rule:''',
                                                        item_line.name)
                                        _logger.info('pricelist lines for unit price inside commodity disc_price %s',
                                                     disc_price)
                                        _logger.info('pricelist lines for unit price inside commodity pricelist %s',
                                                     pricelist_lines[-1].x_product_level_price_pr)
                                        _logger.info('pricelist lines for unit price inside commodity %s', self.price_unit)
                                        val_flag = True
                                    # (qty_breaks.x_product_price_per_value_pr*qty_breaks.x_product_discount_on_level_pr)/100
                            else:
                                self.price_unit = qty_breaks.x_product_price_per_value_pr
                                val_flag = True
                else:
                    for qty_breaks in item_line.x_pricelist_break_cust_qty_price:
                        split_values = qty_breaks.x_product_cust_qty_pr.split('-')
                        if self.product_uom_qty >= float(split_values[0]) and self.product_uom_qty <= float(
                                split_values[1]):
                            self.customer_unit_price = Decimal(qty_breaks.x_product_cust_unit_price).quantize(
                                Decimal('0.00001'), rounding=ROUND_HALF_UP)
                            val_flag = True
                            price_string = ('''Unit price has been fetched from Custom Pricelist rule:''',
                                            item_line.name)
                            _logger.info('pricelist lines for custom unit price %s', self.price_unit)
                            break

            if val_flag == True:
                self.pricing_info = price_string
                break
            # elif self.x_order_master_yards > 0 and self.order_id.pricelist_id and item_line.applied_on != '1_product' and self.product_id and self.order_id.partner_id.x_special_pricing:
            #     for qty_breaks in self.product_id.product_tmpl_id.x_break_qty_price:
            #         split_values = qty_breaks.x_product_qty.split('-')
            #         if self.x_order_master_yards >= float(split_values[0]) and self.x_order_master_yards <= float(split_values[1]):
            #             self.price_unit = qty_breaks.x_product_price_per_value

        for rec in self:
            if val_flag == False:
                _logger.info('INSIDE PRODUCT pricing IF 1')
                if rec.x_order_master_yards > 0 and rec.product_id and not rec.order_id.x_is_sample:
                    _logger.info('INSIDE PRODUCT pricing IF 2')
                    tmpl = rec.product_id.product_tmpl_id.sudo().with_context(active_test=False)
                    for qty_breaks in tmpl.x_break_qty_price:
                        split_values = qty_breaks.x_product_qty.split('-')
                        if rec.x_order_master_yards >= float(split_values[0]) and rec.x_order_master_yards <= float(
                                split_values[1]):
                            rec.price_unit = qty_breaks.x_product_price_per_value

        for item_line in self.order_id.pricelist_id.item_ids:
            if (item_line.applied_on in ['1_product', '4_item_group', '6_price_group', '7_commodity_group']
                    and item_line.x_pricelist_pricing_code == 'FD'
                    and self.x_order_master_yards > 0
                    and self.order_id.pricelist_id
                    and (
                            (item_line.applied_on == '1_product' and item_line.filtered(
                                lambda x: x.product_tmpl_id.id == self.product_id.product_tmpl_id.id))
                            or (
                                    item_line.applied_on == '4_item_group' and item_line.product_item_group_id.id == self.x_sale_line_item_group.id)
                            or (
                                    item_line.applied_on == '6_price_group' and item_line.price_group_id.id == self.product_id.product_tmpl_id.x_product_price_group.id)
                            or (
                                    item_line.applied_on == '7_commodity_group' and item_line.product_commodity_id.id == self.x_sale_line_item_group.x_commodity_class.id)
                    )
                    and (
                            self.order_id.partner_id.x_special_pricing or self.order_id.partner_id.parent_id.x_special_pricing)):
                if item_line.compute_price == 'percentage':
                    for qty_breaks in self.product_id.product_tmpl_id.x_break_qty_price:
                        split_values = qty_breaks.x_product_qty.split('-')
                        if self.x_order_master_yards >= float(split_values[0]) and self.x_order_master_yards <= float(
                                split_values[1]):
                            self.price_unit = qty_breaks.x_product_price_per_value * (1 - item_line.percent_price / 100)
                            if item_line.percent_price < 1:
                                self.price_unit = qty_breaks.x_product_price_per_value * (1 - item_line.percent_price)
                            else:
                                self.price_unit = qty_breaks.x_product_price_per_value * (
                                            1 - item_line.percent_price / 100)
                            break
            if (item_line.applied_on in ['1_product', '4_item_group', '6_price_group', '7_commodity_group']
                    and item_line.x_pricelist_pricing_code == 'FP'
                    and self.x_order_master_yards > 0
                    and self.order_id.pricelist_id
                    and (
                            (item_line.applied_on == '1_product' and item_line.filtered(
                                lambda x: x.product_tmpl_id.id == self.product_id.product_tmpl_id.id))
                            or (
                                    item_line.applied_on == '4_item_group' and item_line.product_item_group_id.id == self.x_sale_line_item_group.id)
                            or (
                                    item_line.applied_on == '6_price_group' and item_line.price_group_id.id == self.product_id.product_tmpl_id.x_product_price_group.id)
                            or (
                                    item_line.applied_on == '7_commodity_group' and item_line.product_commodity_id.id == self.x_sale_line_item_group.x_commodity_class.id)
                    )
                    and (
                            self.order_id.partner_id.x_special_pricing or self.order_id.partner_id.parent_id.x_special_pricing)):
                if item_line.compute_price == 'fixed':
                    self.price_unit = item_line.percent_price
                    break
        return res

    @api.model
    def create(self, vals):
        # Call the super method to create the record
        new_record = super(SaleOrderLine, self).create(vals)

        # Ensure x_order_line_bom is initialized before accessing
        if new_record.x_order_line_bom:
            new_record._compute_master_yards()

        return new_record
