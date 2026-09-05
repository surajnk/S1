from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError
from odoo.tools import float_compare, date_utils, email_split, email_re
from odoo.tools.misc import formatLang, format_date, get_lang

from datetime import date, timedelta
from collections import defaultdict
from itertools import zip_longest
from hashlib import sha256
from json import dumps

import ast
import json
import re
import warnings
import logging

_logger = logging.getLogger(__name__)

class ReconciliationWriteoffWithDiscount(models.AbstractModel):
    _inherit = 'account.reconciliation.widget'

    def _process_move_lines(self, move_line_ids, new_mv_line_dicts):
        move_lines = self.env['account.move.line'].browse(move_line_ids)
        invoice_lines = move_lines.filtered(lambda l: l.move_id.is_invoice())

        for inv_line in invoice_lines:
            invoice = inv_line.move_id
            if (
                invoice.invoice_payment_term_id
                and invoice.invoice_payment_term_id.is_discount
                and invoice.discount_taken == 0
            ):
                payment_date = fields.Date.context_today(self)
                discount_amt, account_id, _ = invoice.invoice_payment_term_id._check_payment_term_discount(
                    invoice=invoice, payment_date=payment_date
                )
                if discount_amt > 0 and account_id:
                    sign = -1 if inv_line.balance < 0 else 1
                    discount_val = {
                        'name': _('Payment Discount'),
                        'account_id': account_id,
                        'journal_id': inv_line.journal_id.id,
                        'debit': sign < 0 and discount_amt or 0.0,
                        'credit': sign > 0 and discount_amt or 0.0,
                        'partner_id': inv_line.partner_id.id,
                    }
                    new_mv_line_dicts.append(discount_val)

                    # ✅ Mark invoice as discount taken
                    invoice.write({'discount_taken': discount_amt})

        # Call original logic
        return super()._process_move_lines(move_line_ids, new_mv_line_dicts)

class AccountMove(models.Model):
    _inherit="account.move"

    # @api.depends(
    #     'line_ids.matched_debit_ids.debit_move_id.move_id.payment_id.is_matched',
    #     'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual',
    #     'line_ids.matched_debit_ids.debit_move_id.move_id.line_ids.amount_residual_currency',
    #     'line_ids.matched_credit_ids.credit_move_id.move_id.payment_id.is_matched',
    #     'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual',
    #     'line_ids.matched_credit_ids.credit_move_id.move_id.line_ids.amount_residual_currency',
    #     'line_ids.debit',
    #     'line_ids.credit',
    #     'line_ids.currency_id',
    #     'line_ids.amount_currency',
    #     'line_ids.amount_residual',
    #     'line_ids.amount_residual_currency',
    #     'line_ids.payment_id.state',
    #     'line_ids.full_reconcile_id')
    # def _compute_amount(self):
    #    res = super(AccountMove, self)._compute_amount()
    #    for move in self.line_ids:
    #         _logger.info("TEST WITHIN INVOICE LINE COMPUTE FUNCTION '%s'",move.price_subtotal)
       # do the things here
       #if self.line_ids.x_invoice_line_labor_items_new:

       # return res

    complaint_ids = fields.One2many(
        'crm.claim', 
        'invoices_ids', 
        string="Complaints",
        compute="_compute_complaint_ids",
        store=False
    )

    complaint_count = fields.Integer(
        string="Complaint Count",
        compute="_compute_complaint_ids",
        store=False
    )

    def _compute_complaint_ids(self):
        for move in self:
            complaints = self.env['crm.claim'].search([
                '|',
                ('invoice_line_ids.move_id', '=', move.id),
                ('invoices_ids', '=', move.id)
            ])
            move.complaint_ids = complaints
            move.complaint_count = len(complaints)

    def action_view_complaints(self):
        """Open the complaints linked to this invoice or vendor bill."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Complaints',
            'view_mode': 'tree,form',
            'res_model': 'crm.claim',
            'domain': [
                '|',
                ('invoice_line_ids.move_id', '=', self.id),
                ('invoices_ids', '=', self.id)
            ],
            'context': {'default_invoices_ids': [(6, 0, [self.id])]},
        }

class AccountMoveLine(models.Model):
    _inherit="account.move.line"

    x_customer_invoice_width = fields.Float('Cust Width',digits='EF Product')
    x_customer_invoice_length = fields.Float('Cust Length',digits='EF Product')
    x_labor_total = fields.Float('Labor Amount')
    x_invoice_line_labor_items_new = fields.One2many('sale.product.labor','x_product_labor_invoice_line','Labor Items')

    @api.model
    def _get_price_total_and_subtotal_model(self, price_unit, quantity, discount, currency, product, partner, taxes, move_type):
        ''' This method is used to compute 'price_total' & 'price_subtotal'.

        :param price_unit:  The current price unit.
        :param quantity:    The current quantity.
        :param discount:    The current discount.
        :param currency:    The line's currency.
        :param product:     The line's product.
        :param partner:     The line's partner.
        :param taxes:       The applied taxes.
        :param move_type:   The type of the move.
        :return:            A dictionary containing 'price_subtotal' & 'price_total'.
        '''
        res = {}
        total_val = 0
        # Compute 'price_subtotal'.
        line_discount_price_unit = price_unit * (1 - (discount / 100.0))
        #subtotal = quantity * line_discount_price_unit

        # for labor_line in self.x_invoice_line_labor_items_new:
        #     total_val += labor_line.x_labor_amount

        if total_val:
            subtotal = quantity * line_discount_price_unit + total_val
        else:
            subtotal = quantity * line_discount_price_unit
        _logger.info("TEST WITHIN INVOICE LINE COMPUTE FUNCTION '%s'",subtotal)
        # Compute 'price_total'.
        if taxes:
            force_sign = -1 if move_type in ('out_invoice', 'in_refund', 'out_receipt') else 1
            taxes_res = taxes._origin.with_context(force_sign=force_sign).compute_all(line_discount_price_unit,
                quantity=quantity, currency=currency, product=product, partner=partner, is_refund=move_type in ('out_refund', 'in_refund'))
            res['price_subtotal'] = taxes_res['total_excluded']
            res['price_total'] = taxes_res['total_included']
        else:
            res['price_total'] = res['price_subtotal'] = subtotal
        #In case of multi currency, round before it's use for computing debit credit
        if currency:
            res = {k: currency.round(v) for k, v in res.items()}
            return res

class SaleProductLabor(models.Model):
    _inherit = "sale.product.labor"

    x_product_labor_invoice_line = fields.Many2one('account.move.line'," Labor Item")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

        #Delivery carrier over-write
    def _create_delivery_line(self, carrier, price_unit):
        SaleOrderLine = self.env['sale.order.line']
        if self.partner_id:
            # set delivery detail in the customer language
            carrier = carrier.with_context(lang=self.partner_id.lang)

        # Apply fiscal position
        taxes = carrier.product_id.taxes_id.filtered(lambda t: t.company_id.id == self.company_id.id)
        taxes_ids = taxes.ids
        if self.partner_id and self.fiscal_position_id:
            taxes_ids = self.fiscal_position_id.map_tax(taxes, carrier.product_id, self.partner_id).ids

        # Create the sales order line
        carrier_with_partner_lang = carrier.with_context(lang=self.partner_id.lang)
        if carrier_with_partner_lang.product_id.description_sale:
            so_description = '%s: %s' % (carrier_with_partner_lang.name,
                                        carrier_with_partner_lang.product_id.description_sale)
        else:
            so_description = carrier_with_partner_lang.name
        values = {
            'order_id': self.id,
            'name': so_description,
            'x_customer_order_width':0,
            'x_order_customer_uom':1,
            'product_uom_qty': 1,
            'product_uom': carrier.product_id.uom_id.id,
            'product_id': carrier.product_id.id,
            'tax_id': [(6, 0, taxes_ids)],
            'is_delivery': True,
        }
        if carrier.invoice_policy == 'real':
            values['price_unit'] = 0
            values['name'] += _(' (Estimated Cost: %s )', self._format_currency_amount(price_unit))
        else:
            values['price_unit'] = price_unit
        if carrier.free_over and self.currency_id.is_zero(price_unit) :
            values['name'] += '\n' + 'Free Shipping'
        if self.order_line:
            values['sequence'] = self.order_line[-1].sequence + 1
        sol = SaleOrderLine.sudo().create(values)
        return sol

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self, **optional_values):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        :param optional_values: any parameter that should be added to the returned invoice line
        """
        item_line = []
        self.ensure_one()
        # _logger.info("LABOR ITEM '%s'",self.x_order_line_labor_items_grid_new.x_product_product_labor.name)
        if self.x_order_line_labor_items_grid_new:
            labour_total = 0
            for item_val in self.x_order_line_labor_items_grid_new.filtered(lambda a: a.x_product_labor_select == True):
                #_logger.info("LABOR ITEM '%s'",item_val.x_labor_monetary_amount)
                item_line.append(
                    (0,0,{
                        'x_product_product_labor':item_val.x_product_product_labor,
                        'x_labor_amount':item_val.x_labor_amount,
                        'x_labor_unit_req':item_val.x_labor_unit_req,
                        })
                    )
                    
        res = {
            'display_type': self.display_type,
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.x_order_customer_uom.id,
            'x_customer_invoice_width':self.x_customer_order_width,
            'x_customer_invoice_length':self.x_customer_order_length,
            'quantity': self.qty_to_invoice,
            'discount': self.discount,
            'price_unit': self.customer_unit_price,
            'tax_ids': [(6, 0, self.tax_id.ids)],
            'analytic_account_id': self.order_id.analytic_account_id.id,
            'analytic_tag_ids': [(6, 0, self.analytic_tag_ids.ids)],
            'sale_line_ids': [(4, self.id)],
            'x_invoice_line_labor_items_new':item_line
        }
        if optional_values:
            res.update(optional_values)
        if self.display_type:
            res['account_id'] = False
        return res
