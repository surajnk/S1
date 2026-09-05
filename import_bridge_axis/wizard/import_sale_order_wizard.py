# -*- coding: utf-8 -*-
#################################################################################
# Author      : AxisTechnolabs.com
# Copyright(c): 2011-Axistechnolabs.com.
# All Rights Reserved.
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#################################################################################
from odoo import models, fields, _,api
from odoo.exceptions import Warning
import logging
import tempfile
import binascii
import datetime

_logger = logging.getLogger(__name__)
import io
import re

try:
    import csv
except ImportError:
    _logger.debug('Cannot `import csv`.')
try:
    import xlrd
except ImportError:
    _logger.debug('Cannot `import xls`.')
try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')


class ImportSaleOrder(models.TransientModel):
    _name = "import.sale.order"
    _description = 'import sale order'

    import_file = fields.Binary(string="Add File")
    file_option = fields.Selection([('csv', 'CSV File'), ('xls', 'XLS File')], string='Select File', default='csv')
    sequence_option = fields.Selection([('default_sequence', 'Use System Default Sequence Number'),
                                        ('file_sequence', 'Use Excel/CSV Sequence Number')], string='Sequence Option',
                                       default='default_sequence')

    quotation_stage_option = fields.Selection(
        [('draft_quotation', 'Import Draft Quotation'),
         ('validate_quotation', 'Validate Quotation Automatically With Import')],
        string='Quotation Stage Option', default='draft_quotation')
    product_by = fields.Selection([('name', 'Name'), ('code', 'Default Code'), ('barcode', 'Barcode')],
                                  string='Import Product By', default='name')
    
    def import_sale_order(self):
        if self.file_option == 'csv':
           
            csv_data = base64.b64decode(self.import_file)
            data_file = io.StringIO(csv_data.decode("utf-8"))
            data_file.seek(0)
            csv_reader = csv.DictReader(data_file, delimiter=',')
            

            partner = self.env['res.partner']
            payment_term = self.env['account.payment.term']
            product = self.env['product.product']
            user = self.env['res.users']
            tax = self.env['account.tax']
            lst =[]
            for line in csv_reader:

                if line.get('Partner'):
                    partner = partner.search([('name', '=', line.get('Partner'))])
                    if not partner:
                        partner = partner.create({
                            'name': line.get('Partner'),
                        })
                    partner_count = self.env['res.partner'].sudo().search_count([('name', '=', line.get('Partner'))])
                    lst.append(partner_count)

                if line.get('Payment Terms'):

                    payment_term = payment_term.search([('name', '=', line.get('Payment Terms'))])
                    amount = [int(i) for i in line.get('Payment Terms').split() if i.isdigit()]

                    if not payment_term:
                        payment_term = payment_term.create({
                            'name': line.get('Payment Terms'),
                            'line_ids': [
                                (0, 0, {
                                    'value': 'balance',
                                    'days': amount[0],
                                    'option': 'day_after_invoice_date',
                                    'day_of_the_month': 0,
                                }),
                            ]
                        })

                if line.get('Date'):
                    date = datetime.datetime.strptime(line['Date'], '%m/%d/%Y')
                else:
                    date = datetime.datetime.now()

                if line.get('Salesperson'):
                    user = user.search([('name', '=', line.get('Salesperson'))])

                if line.get('Tax'):
                    amount = re.findall(r"[-+]?\d*\.\d+|\d+", line.get('Tax'))
                    customer_tax = tax.search(
                        [('name', '=', line.get('Tax')), ('type_tax_use', '=', 'sale')])

                    if not customer_tax:
                        customer_tax = customer_tax.create({
                            'name': line.get('Tax'),
                            'type_tax_use': 'sale',
                            'amount': amount[0],
                            'active': True,
                        })

                if line.get('Uom'):
                    uom = self.env['uom.uom'].search([('name', '=', line.get('Uom'))])

                

                sale_order = self.env['sale.order'].search([('name', '=', line.get('Order'))])
                if not sale_order:
                    if self.sequence_option == 'default_sequence':
                        sale_order = self.env['sale.order'].create({
                            'partner_id': partner.id,
                            'date_order': date,
                            'payment_term_id': payment_term.id,
                            'user_id': user.id,
                        })

                    elif self.sequence_option == 'file_sequence':
                        sale_order = self.env['sale.order'].create({
                            'name': line.get('Order') if line.get('Order') else 'SO',
                            'partner_id': partner.id,
                            'date_order': date,
                            'payment_term_id': payment_term.id,
                            'user_id': user.id,
                        })

                if sale_order:

                    if sale_order and line.get('Product'):

                        if self.product_by == 'name':
                            product = product.search([('name', '=', line.get('Product'))])
                            if not product:
                                product = product.create({
                                    'name': line.get('Product'),
                                })

                        if self.product_by == 'code':
                            product = product.search([('default_code', '=', line.get('Product'))])
                        

                        if self.product_by == 'barcode':
                            product = product.search([('barcode', '=', line.get('Product'))])
                           

                        if product:
                            sale_order[0].write({
                                'order_line': [
                                    (0, 0, {
                                        'name': line.get('Description'),
                                        'product_id': product.id,
                                        'product_uom': 1,
                                        'product_uom_qty': float(line.get('Quantity')) if line.get('Quantity') else 1.0,
                                        'price_unit': float(line.get('Price')),
                                        'tax_id': customer_tax,
                                        'order_id': sale_order,
                                    }),
                                ]
                            })

                        if self.quotation_stage_option == 'validate_quotation':
                            sale_order.action_confirm()
            get_count=0
            for rec in lst:
                get_count = get_count+rec
                    
            model = self.env.context.get('active_model')
            if model == 'custom.dashboard':
               sale_info = self.env['custom.dashboard'].sudo().search([['name','=','Sale']])
               if sale_info.count == 0:
                  sale_info.count = get_count
               else:
                  sale_info.count += get_count

        elif self.file_option == 'xls':
            fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            fp.write(binascii.a2b_base64(self.import_file))
            fp.seek(0)
            workbook = xlrd.open_workbook(fp.name)
            sheet = workbook.sheet_by_index(0)
            keys = sheet.row_values(0)
            xls_reader = [sheet.row_values(i) for i in range(1, sheet.nrows)]

            

            partner = self.env['res.partner']
            payment_term = self.env['account.payment.term']
            product = self.env['product.product']
            user = self.env['res.users']
            tax = self.env['account.tax']
            lst =[]
            for row in xls_reader:
                line = dict(zip(keys, row))
                if line.get('Partner'):
                    partner = partner.search([('name', '=', line.get('Partner'))])
                    if not partner:
                        partner = partner.create({
                            'name': line.get('Partner'),
                        })
                    partner_count = self.env['res.partner'].sudo().search_count([('name', '=', line.get('Partner'))])
                    lst.append(partner_count)

                if line.get('Payment Terms'):

                    payment_term = payment_term.search([('name', '=', line.get('Payment Terms'))])
                    amount = [int(i) for i in line.get('Payment Terms').split() if i.isdigit()]

                    if not payment_term:
                        payment_term = payment_term.create({
                            'name': line.get('Payment Terms'),
                            'line_ids': [
                                (0, 0, {
                                    'value': 'balance',
                                    'days': amount[0],
                                    'option': 'day_after_invoice_date',
                                    'day_of_the_month': 0,
                                }),
                            ]
                        })

                if line.get('Date'):
                    date = datetime.datetime.strptime(line['Date'], '%m/%d/%Y')
                else:
                    date = datetime.datetime.now()

                if line.get('Salesperson'):
                    user = user.search([('name', '=', line.get('Salesperson'))])

                if line.get('Tax'):

                    amount = re.findall(r"[-+]?\d*\.\d+|\d+", line.get('Tax'))
                    customer_tax = tax.search(
                        [('name', '=', line.get('Tax')), ('type_tax_use', '=', 'sale')])

                    if not customer_tax:
                        customer_tax = customer_tax.create({
                            'name': line.get('Tax'),
                            'type_tax_use': 'sale',
                            'amount': amount[0],
                            'active': True,
                        })

                if line.get('Uom'):
                    uom = self.env['uom.uom'].search([('name', '=', line.get('Uom'))])

                    

                sale_order = self.env['sale.order'].search([('name', '=', line.get('Order'))])
                if not sale_order:
                    if self.sequence_option == 'default_sequence':
                        sale_order = self.env['sale.order'].create({
                            'partner_id': partner.id,
                            'date_order': date,
                            'payment_term_id': payment_term.id,
                            'user_id': user.id,
                        })

                    elif self.sequence_option == 'file_sequence':
                        sale_order = self.env['sale.order'].create({
                            'name': line.get('Order') if line.get('Order') else 'SO',
                            'partner_id': partner.id,
                            'date_order': date,
                            'payment_term_id': payment_term.id,
                            'user_id': user.id,
                        })

                if sale_order:

                    if sale_order and line.get('Product'):

                        if self.product_by == 'name':
                            product = product.search([('name', '=', line.get('Product'))])
                            if not product:
                                product = product.create({
                                    'name': line.get('Product'),
                                })

                        if self.product_by == 'code':
                            product = product.search([('default_code', '=', line.get('Product'))])
                            if not product:
                                product = product.create({
                                    'name': line.get('Product'),
                                })

                        if self.product_by == 'barcode':
                            product = product.search([('barcode', '=', line.get('Product'))])
                            if not product:
                                product = product.create({
                                    'name': line.get('Product'),
                                })

                        if product:
                            sale_order[0].write({
                                'order_line': [
                                    (0, 0, {
                                        'name': line.get('Description'),
                                        'product_id': product.id,
                                        'product_uom': 1,
                                        'product_uom_qty': float(line.get('Quantity')) if line.get('Quantity') else 1.0,
                                        'price_unit': float(line.get('Price')),
                                        'tax_id': customer_tax,
                                        'order_id': sale_order,
                                    }),
                                ]
                            })

                        if self.quotation_stage_option == 'validate_quotation':
                            sale_order.action_confirm()
            get_count=0
            for rec in lst:
                get_count = get_count+rec
                
            model = self.env.context.get('active_model')
            if model == 'custom.dashboard':
               sale_info = self.env['custom.dashboard'].sudo().search([['name','=','Sale']])
               if sale_info.count == 0:
                  sale_info.count = get_count
               else:
                  sale_info.count += get_count