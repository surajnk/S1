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
from odoo import models, fields, _
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
    _logger.debug('Cannot `import Excel`.')
try:
    import base64
except ImportError:
    _logger.debug('Cannot `import base64`.')


class ImportClient(models.TransientModel):
    _name = "import.inventory.adjustment"
    _description = 'import inventory adjustment'

    inventory_name = fields.Char(string='Inventory Name')
    location = fields.Many2one('stock.location', string='Location')
    product_new = fields.Many2one('product.product',string='product')
    import_serial = fields.Boolean(string='Import serial/Lot number with expire date',default=True)
    import_location = fields.Boolean(string='Import Location on line',default=True)
    import_file = fields.Binary(string="Add File")
    product_by = fields.Selection([('name', 'Name'), ('code', 'Default Code'), ('barcode', 'Barcode')],
                                  string='Import Product By', default='name')
    file_option = fields.Selection([('csv', 'CSV File'), ('xls', 'XLS File')], string='Select File', default='csv')

    def detect_delimiter(self,sample_line):
        # If the line contains more commas than pipes, assume it's comma-delimited
        if sample_line.count(',') > sample_line.count('|'):
            return ','
        else:
            return '|'

    def import_inventory_adjustment_action(self):
        if self.file_option == 'csv':
            try:
                csv_data = base64.b64decode(self.import_file)
                data_file = io.StringIO(csv_data.decode("utf-8"))
                sample_line = data_file.readline()
                delimiter = self.detect_delimiter(sample_line)
                _logger.info("Detected delimiter: %s", delimiter)
                data_file.seek(0)  # Go back to the start of the file after reading the first line
                csv_reader = csv.DictReader(data_file, delimiter=delimiter)
            except Exception as e:
                _logger.info("Error decoding or reading the CSV file: %s", e)
                raise Warning(_("Invalid file!"))
           
            product = self.env['product.product']
            stock_info = self.env['stock.inventory']
            package_info = self.env['stock.quant.package']
            location_info= self.env['stock.location']
            fin_location_info= self.env['stock.location']
            location_info1= self.env['stock.location']
            location_info2= self.env['stock.location']
            lot_number = self.env['stock.production.lot']
            lst =[]

            inventory = self.env['stock.inventory'].create({
                'name': self.inventory_name,
                # 'location_ids': [(4, self.location.id)],
                'product_ids' :product.ids,
               
            })

            for line in csv_reader:

                if line.get('Product Name'):
                    if self.product_by == 'name':
                        product = product.search([('name', '=', line.get('Product Name'))])
                        if not product:
                            raise Warning(_("Invalid Product '%s'",line.get('Product Name')))
                            # product = product.create({
                            #     'name': line.get('Product Name'),
                            # })
                        partner_count = product.sudo().search_count([('name', '=', line.get('Product Name'))])
                        lst.append(partner_count)


                    if self.product_by == 'code':
                        product = product.search([('code', '=', line.get('Product Code'))])
                           

                    if self.product_by == 'barcode':
                        product = product.search([('barcode', '=', line.get('Product Barcode'))])

                if line.get('Second Section'):
                    location_info2 = location_info.search([('name', '=', line.get('Second Section')),('usage', '=', 'view')])
                    if location_info2 and line.get('First Section'):
                        location_info1 = location_info.search([('name', '=', line.get('First Section')),('location_id', '=', location_info2.id)])
                        _logger.info("LOCATIONNN INFOOOO111111 %s", location_info1.name)
                        if location_info1.location_id.id == location_info2.id:
                            if line.get('Location'):
                                location_info = location_info.search([('name', '=', line.get('Location')),('location_id', '=', location_info1.id)])
                                _logger.info("LOCATIONNN INFOOOO %s", location_info.name)
                                if location_info.location_id.id == location_info1.id:
                                    fin_location_info = location_info
                                if not fin_location_info:
                                    raise Warning(_("Invalid Location '%s'",line.get('Location')))
                        if not location_info1:
                            raise Warning(_("Invalid First Section!"))
                    if location_info2 and not line.get('First Section'):
                        if line.get('Location'):
                            location_info = location_info.search([('name', '=', line.get('Location')),('location_id', '=', location_info2.id)])
                            if location_info.location_id.id == location_info2.id:
                                fin_location_info = location_info
                            if not fin_location_info:
                                raise Warning(_("Invalid Location!"))
                    if not location_info2:
                        raise Warning(_("Invalid Second Section!"))

                    # if location_info2 and not line.get('First Section'):

                    #     location_info1 = location_info.search([('name', '=', line.get('Second Section'))])
                    #     if line.get('Location'):
                    #         location_info = location_info.search([('name', '=', line.get('Location'))])
                    #         if line.get('First Section'):
                    #             location_info1 = location_info.search([('name', '=', line.get('First Section')), ('location_id', '=', location_info.id)])
                    #         if not location_info:
                    #             location_info = location_info.create({
                    #                 'name': line.get('Location'),
                    #             })

                if line.get('Lot Serial Number'):
                    lot_number = lot_number.search([('name', '=', line.get('Lot Serial Number')), ('product_id', '=', product.id)])
                    if not lot_number and self.import_serial:
                        lot_number = lot_number.create({
                            'name': line.get('Lot Serial Number'),
                            'product_id': product.id,
                            'company_id': self.env.company.id,
                        })
                # if line.get('Lot Serial Number'):
                #     lot_number = lot_number.search([('name', '=', line.get('Lot Serial Number'))])
                    # if not lot_number:
                    #     lot_number  = lot_number.create({'name':line.get('Package'),'product_qty':line.get('Quantity'),'product_id':product.id,'company_id':  self.env.company.id,})
                  

                if line.get('Package'):
                    package_info = package_info.search([('name', '=', line.get('Package'))])
                    if not package_info:
                        package_info = package_info.create({
                            'name': line.get('Package'),
                        })     
                       
                if line.get('Date'):
                    date = datetime.datetime.strptime(line['Date'], '%m/%d/%Y')
                else:
                    date = datetime.datetime.now()

                if len(product) > 1:
                    continue

                inventory.action_start()
                if self.import_location == True:
                    info = self.env['stock.inventory.line'].create({
                        'product_id': product.id,
                        'inventory_id': inventory.id,
                        'location_id': fin_location_info.id,
                        'inventory_date': date,
                        'prod_lot_id':lot_number.id,
                        'unit_price':line.get('Cost Price'),
                        'package_id':package_info.id,
                        'product_qty': line.get('Quantity'),
                    })
                # if self.import_serial == True:
                #     info_serial = self.env['stock.production.lot'].create({
                #         'product_id': product.id,
                #         'name':line.get('Lot Serial Number'),
                #         'company_id':  self.env.company.id,
                       
                #     })
            get_count=0
            for rec in lst:
                get_count = get_count+rec
                
            model = self.env.context.get('active_model')
            if model == 'custom.dashboard':
               vendor_info = self.env['custom.dashboard'].sudo().search([['name','=','Inventory Adjustment']])
               if vendor_info.count == 0:
                  vendor_info.count = get_count
               else:
                  vendor_info.count += get_count




        elif self.file_option == 'xls':
            fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            fp.write(binascii.a2b_base64(self.import_file))
            fp.seek(0)
            workbook = xlrd.open_workbook(fp.name)
            sheet = workbook.sheet_by_index(0)
            keys = sheet.row_values(0)
            xls_reader = [sheet.row_values(i) for i in range(1, sheet.nrows)]
           

            product = self.env['product.product']
            stock_info = self.env['stock.inventory']
            package_info = self.env['stock.quant.package']
            location_info= self.env['stock.location']
            lot_number = self.env['stock.production.lot']
            lst =[]
           

            for row in xls_reader:
                line = dict(zip(keys, row))

                if line.get('Location'):
                    location_info = location_info.search([('name', '=', line.get('Location'))])
                    if not location_info:
                        location_info = location_info.create({
                            'name': line.get('Location'),
                        })

              
                if line.get('Lot Serial Number'):
                    lot_number = lot_number.search([('name', '=', line.get('Lot Serial Number'))])
                  

                if line.get('Package'):
                    package_info = package_info.search([('name', '=', line.get('Package'))])
                    if not package_info:
                        package_info = package_info.create({
                            'name': line.get('Package'),
                        })     
                       
                if line.get('Date'):
                    date = datetime.datetime.strptime(line['Date'], '%m/%d/%Y')
                else:
                    date = datetime.datetime.now()

                if line.get('Product Name'):
                    if self.product_by == 'name':
                        product = product.search([('name', '=', line.get('Product Name'))])
                        if not product:
                            product = product.create({
                                'name': line.get('Product Name'),
                            })
                        partner_count = product.sudo().search_count([('name', '=', line.get('Product Name'))])
                        lst.append(partner_count)

                    if self.product_by == 'code':
                        product = product.search([('code', '=', line.get('Product Code'))])
                           

                    if self.product_by == 'barcode':
                        product = product.search([('barcode', '=', line.get('Product Barcode'))])

                inventory = self.env['stock.inventory'].create({
                    'name': self.inventory_name,
                    'location_ids': [(4, self.location.id)],
                    'product_ids' :product.ids,
                    
                   
                })
                inventory.action_start()
                if self.import_location == True:
                    info = self.env['stock.inventory.line'].create({
                        'product_id': product.id,
                        'inventory_id': inventory.id,
                        'location_id': inventory.location_ids[0].id,
                        'inventory_date': date,
                        'prod_lot_id':lot_number.id,
                        'package_id':package_info.id,
                        'theoretical_qty': line.get('Quantity'),
                    })

                if self.import_serial == True:
                    info_serial = self.env['stock.production.lot'].create({
                        'product_id': product.id,
                        'name':line.get('Lot Serial Number'),
                        'company_id':  self.env.company.id,
                       
                    })
            get_count=0
            for rec in lst:
                get_count = get_count+rec
                
            model = self.env.context.get('active_model')
            if model == 'custom.dashboard':
               vendor_info = self.env['custom.dashboard'].sudo().search([['name','=','Inventory Adjustment']])
               if vendor_info.count == 0:
                  vendor_info.count = get_count
               else:
                  vendor_info.count += get_count
          

        else:
            raise Warning(_("Invalid file!"))


     