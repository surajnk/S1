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
import datetime

import tempfile
import binascii
import re
import csv
import xlrd
import base64
import io
import logging

_logger = logging.getLogger(__name__)


class ImportBOM(models.TransientModel):
    _name = "import.bom"
    _description = 'import bom'

    import_file = fields.Binary(string="Add File")
    file_option = fields.Selection([('csv', 'CSV File'), ('xls', 'XLS File')], string='Select File', default='csv')
    bom_type = fields.Selection([('normal', 'Normal'), ('phantom', 'Phantom')], string='BOM Type', default='normal')

    def detect_delimiter(self,sample_line):
        # If the line contains more commas than pipes, assume it's comma-delimited
        if sample_line.count(',') > sample_line.count('|'):
            return ','
        else:
            return '|'

    def import_bom(self):
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
            product_model = self.env['product.product']
            mrp_bom_model = self.env['mrp.bom']
            uom_model = self.env['uom.uom']
            branch = self.env['res.branch']
            bom_operations = []
            bom_lines = []
            workcenter_capacities = []
            current_main_product = None
            product_template = None
            bom = None
            product_main_qty = None
            branch_val = None
            branch_v = None
            uom_main = uom_model

            for line in csv_reader:
                main_product = line.get('Main Product')
                _logger.info("Processing Main Product: %s", main_product)

                # Check if a new main product is encountered
                if main_product and main_product != current_main_product:
                    _logger.info("New main product detected: %s", main_product)
                    # If there's an existing product, create the BoM for it
                    if current_main_product:
                        _logger.info("Creating BoM for %s", current_main_product)
                        self.create_bom(product_template, product_main_qty, branch_v, uom_main, bom_lines, bom_operations)
                    
                    # Start processing the new main product
                    current_main_product = main_product
                    bom_lines = []
                    bom_operations = []
                    product_template = self.env['product.template'].search([('name', '=', main_product)], limit=1)
                    if not product_template:
                        raise Warning(_("Main Product '%s' not found.") % (main_product))
                        _logger.info("Product template not found, creating new template for %s", main_product)
                        product_template = self.env['product.template'].create({'name': main_product})

                if line.get('Main Product Qty'):
                    product_main_qty = line.get('Main Product Qty')
                    _logger.info("Main Product Qty: %s", product_main_qty)

                if line.get('Branch'):
                    branch_v = branch.search([('name', '=', line.get('Branch'))], limit=1)
                    if not branch_v:
                        raise Warning(_("Branch '%s' not found.") % (line.get('Branch')))
                        _logger.info("Branch '%s' not found, creating new branch", line.get('Branch'))
                        branch_v = branch.create({'name': line.get('Branch')})
                    _logger.info("Branch: %s", branch_v.name)

                if line.get('UOM'):
                    uom_main = uom_model.search([('name', '=', line.get('UOM'))])
                    _logger.info("UOM: %s", uom_main.name if uom_main else 'Not found')

                uom = uom_main
                # Process components and associated operations
                if line.get('BoM Lines/Component') and line.get('Material Product Qty'):  # Ensure non-empty component and quantity
                    _logger.info("Processing component: %s", line.get('BoM Lines/Component'))
                    component_product = product_model.search([('name', '=', line.get('BoM Lines/Component'))], limit=1)
                    if not component_product:
                        raise Warning(_("Component '%s' not found.") % (line.get('BoM Lines/Component')))
                        _logger.info("Component '%s' not found, creating new product", line.get('BoM Lines/Component'))
                        component_product = product_model.create({'name': line.get('BoM Lines/Component')})
                    
                    if line.get('BoM Lines/Multiple Operations'):
                        uom = uom_model.search([('name', '=', line.get('BoM Lines/Product Unit of Measure'))], limit=1)
                        if not uom:
                            raise Warning(_("Unit of Measure '%s' not found.") % line.get('BoM Lines/Product Unit of Measure'))
                        _logger.info("UOM for component: %s", uom.name)

                    # Initialize the many2many field for operations related to this component
                    workcenter_capacities = []

                    # Process operations specific to this component
                    if line.get('BoM Lines/Multiple Operations'):
                        operations = line.get('BoM Lines/Multiple Operations').split(',')
                        _logger.info("Processing operations for component: %s", operations)

                        for operation_entry in operations:
                            try:
                                operation_name, workcenter_name = operation_entry.split('-')
                                _logger.info("Operation: %s, Workcenter: %s", operation_name, workcenter_name)

                                # Search for the workcenter
                                work_center = self.env['mrp.workcenter'].search([('name', '=', workcenter_name.strip())])
                                if not work_center:
                                    raise Warning(_("Work Center '%s' not found.") % workcenter_name)

                                # Search for the operation linked to this workcenter
                                operation = self.env['mrp.routing.workcenter'].search([
                                    ('name', '=', operation_name.strip()),
                                    ('workcenter_id', '=', work_center.id),
                                    '|', ('bom_id', '=', False), ('bom_id', '=', None)
                                ])
                                if not operation:
                                    raise Warning(_("Operation '%s' not found for Work Center '%s'.") % (operation_name, workcenter_name))

                                # Add the operation to the many2many field list
                                workcenter_capacities.append((4, operation.id))
                            except Exception as e:
                                _logger.info("Error processing operation entry '%s': %s", operation_entry, e)

                    # Add the component to the BoM lines with its operations
                    _logger.info("Adding component %s with quantity %s to BoM lines", line.get('BoM Lines/Component'), line.get('Material Product Qty'))
                    bom_lines.append((0, 0, {
                        'product_id': component_product.id,
                        'product_qty': float(line.get('Material Product Qty')),
                        'product_uom_id': uom.id,
                        'workcenter_capacities': workcenter_capacities,  # Assign the many2many field
                    }))

                # Process general operations not tied to specific components
                if line.get('Operations/Select from Existing Operations/Display Name'):
                    _logger.info("Processing general operation: %s", line.get('Operations/Select from Existing Operations/Display Name'))
                    work_center = self.env['mrp.workcenter'].search([('name', '=', line.get('Operations/Work Center'))], limit=1)
                    if not work_center:
                        raise Warning(_("Work Center '%s' not found.") % line.get('Operations/Work Center'))
                    
                    operation = self.env['mrp.routing.workcenter'].search([
                        ('name', '=', line.get('Operations/Select from Existing Operations/Display Name')),
                        ('workcenter_id', '=', work_center.id)
                    ], limit=1)
                    if not operation:
                        raise Warning(_("Operation '%s' not found for Work Center '%s'.") % (line.get('Operations/Select from Existing Operations/Display Name'), line.get('Operations/Work Center')))
                    
                    bom_operations.append((0, 0, {
                        'workcenter_id': work_center.id,
                        'exist_workcenter_id': operation.id,
                        'name': line.get('Operations/Select from Existing Operations/Display Name'),
                        'capacity': operation.capacity,
                        'sequence': operation.sequence,
                        'time_start': float(line.get('Operations/Time Before Prod') or 0),
                    }))

            # Finalize the last product's BoM
            if current_main_product:
                _logger.info("Finalizing BoM for %s", current_main_product)
                self.create_bom(product_template, product_main_qty, branch_v, uom_main, bom_lines, bom_operations)

    def create_bom(self, product_template, product_main_qty, branch_v, uom_main, bom_lines, bom_operations):
        _logger.info("Creating or updating BoM for product: %s", product_template.name)
        mrp_bom_model = self.env['mrp.bom']
        bom = mrp_bom_model.search([('product_tmpl_id', '=', product_template.id)], limit=1)
        if not bom:
            _logger.info("BoM not found, creating a new one.")
            bom = mrp_bom_model.create({
                'product_tmpl_id': product_template.id,
                'product_uom_id': uom_main.id,
                'product_qty': product_main_qty,
                'branch_id': branch_v.id,
                'type': self.bom_type,
                'bom_line_ids': bom_lines,
                'operation_ids': bom_operations,
            })
        else:
            _logger.info("Updating existing BoM (appending new lines/operations only).")
            existing_product_ids = bom.bom_line_ids.mapped('product_id.id')
            new_lines = [l for l in bom_lines if l[2]['product_id'] not in existing_product_ids]

            existing_op_names = bom.operation_ids.mapped('name')
            new_ops = [o for o in bom_operations if o[2]['name'] not in existing_op_names]

            if new_lines:
                bom.write({'bom_line_ids': new_lines})
            if new_ops:
                bom.write({'operation_ids': new_ops})



    #Working Aug29 - 2024
    # def import_bom(self):
    #     if self.file_option == 'csv':
    #         try:
    #             csv_data = base64.b64decode(self.import_file)
    #             data_file = io.StringIO(csv_data.decode("utf-8"))
    #             data_file.seek(0)
    #             csv_reader = csv.DictReader(data_file, delimiter=',')
    #         except:
    #             raise Warning(_("Invalid file!"))

    #         product_model = self.env['product.product']
    #         mrp_bom_model = self.env['mrp.bom']
    #         uom_model = self.env['uom.uom']
    #         branch = self.env['res.branch']
    #         bom_operations = []
    #         bom_lines = []
    #         workcenter_capacities = []
    #         current_main_product = None
    #         product_template = None
    #         bom = None
    #         product_main_qty = None
    #         branch_val = None

    #         for line in csv_reader:
    #             main_product = line.get('Main Product')

    #             # Check if a new main product is encountered
    #             if main_product and main_product != current_main_product:
    #                 # If there's an existing product, create the BoM for it
    #                 if current_main_product:
    #                     self.create_bom(product_template, product_main_qty,branch_v,uom_main, bom_lines, bom_operations)
                    
    #                 # Start processing the new main product
    #                 current_main_product = main_product
    #                 bom_lines = []
    #                 bom_operations = []
    #                 product_template = self.env['product.template'].search([('name', '=', main_product)], limit=1)
    #                 if not product_template:
    #                     product_template = self.env['product.template'].create({'name': main_product})

    #             if line.get('Main Product Qty'):
    #                 product_main_qty = line.get('Main Product Qty')

    #             if line.get('Branch'):
    #                 branch_v = branch.search([('name', '=', line.get('Branch'))], limit=1)
    #                 if not branch_v:
    #                     branch_v = branch.create({'name': line.get('Branch')})

    #             if line.get('UOM'):
    #                 uom_main = uom_model.search([('name', '=', line.get('UOM'))])
    #             # Process components and associated operations
    #             if line.get('BoM Lines/Component'):
    #                 component_product = product_model.search([('name', '=', line.get('BoM Lines/Component'))], limit=1)
    #                 if not component_product:
    #                     component_product = product_model.create({'name': line.get('BoM Lines/Component')})
                    
    #                 if line.get('BoM Lines/Multiple Operations'):
    #                     uom = uom_model.search([('name', '=', line.get('BoM Lines/Product Unit of Measure'))], limit=1)
    #                     if not uom:
    #                         raise Warning(_("Unit of Measure '%s' not found.") % line.get('BoM Lines/Product Unit of Measure'))
    #                 # Initialize the many2many field for operations related to this component
    #                 workcenter_capacities = []

    #                 # Process operations specific to this component
    #                 if line.get('BoM Lines/Multiple Operations'):
    #                     operations = line.get('BoM Lines/Multiple Operations').split(',')

    #                     for operation_entry in operations:
    #                         operation_name, workcenter_name = operation_entry.split('-')

    #                         # Search for the workcenter
    #                         work_center = self.env['mrp.workcenter'].search([('name', '=', workcenter_name.strip())])
    #                         if not work_center:
    #                             raise Warning(_("Work Center '%s' not found.") % workcenter_name)

    #                         # Search for the operation linked to this workcenter
    #                         operation = self.env['mrp.routing.workcenter'].search([
    #                             ('name', '=', operation_name.strip()),
    #                             ('workcenter_id', '=', work_center.id),'|',('bom_id', '=', False),('bom_id', '=', None)
    #                         ])
    #                         if not operation:
    #                             raise Warning(_("Operation '%s' not found for Work Center '%s'.") % (operation_name, workcenter_name))

    #                         # Add the operation to the many2many field list
    #                         workcenter_capacities.append((4, operation.id))

    #                 # Add the component to the BoM lines with its operations
    #                 if line.get('Material Product Qty'):
    #                     bom_lines.append((0, 0, {
    #                         'product_id': component_product.id,
    #                         'product_qty': float(line.get('Material Product Qty')),
    #                         'product_uom_id': uom.id,
    #                         'workcenter_capacities': workcenter_capacities,  # Assign the many2many field
    #                     }))

    #             # Process general operations not tied to specific components
    #             if line.get('Operations/Select from Existing Operations/Display Name'):
    #                 work_center = self.env['mrp.workcenter'].search([('name', '=', line.get('Operations/Work Center'))], limit=1)
    #                 if not work_center:
    #                     raise Warning(_("Work Center '%s' not found.") % line.get('Operations/Work Center'))
                    
    #                 operation = self.env['mrp.routing.workcenter'].search([
    #                     ('name', '=', line.get('Operations/Select from Existing Operations/Display Name')),
    #                     ('workcenter_id', '=', work_center.id)
    #                 ], limit=1)
    #                 if not operation:
    #                     raise Warning(_("Operation '%s' not found for Work Center '%s'.") % (line.get('Operations/Select from Existing Operations/Display Name'), line.get('Operations/Work Center')))
                    
    #                 bom_operations.append((0, 0, {
    #                     'workcenter_id': work_center.id,
    #                     'exist_workcenter_id': operation.id,
    #                     'name': line.get('Operations/Select from Existing Operations/Display Name'),
    #                     'capacity':operation.capacity,
    #                     'sequence':operation.sequence,
    #                 }))

    #         # Finalize the last product's BoM
    #         if current_main_product:
    #             self.create_bom(product_template, product_main_qty, branch_v,uom_main, bom_lines, bom_operations)

    # def create_bom(self, product_template, product_main_qty,branch_v,uom_main, bom_lines, bom_operations):
    #     mrp_bom_model = self.env['mrp.bom']
    #     bom = mrp_bom_model.search([('product_tmpl_id', '=', product_template.id)], limit=1)
    #     if not bom:
    #         bom = mrp_bom_model.create({
    #             'product_tmpl_id': product_template.id,
    #             'product_uom_id': uom_main.id,
    #             'product_qty': product_main_qty,  # Set a default quantity, adjust if necessary
    #             'branch_id': branch_v.id,
    #             'type': self.bom_type,
    #             'bom_line_ids': bom_lines,
    #             'operation_ids': bom_operations,
    #         })
    #     else:
    #         bom.write({
    #             'bom_line_ids': bom_lines,
    #             'operation_ids': bom_operations,
    #         })
#OLD

    
    # def import_bom(self):
    #     if self.file_option == 'csv':
    #         try:
    #             csv_data = base64.b64decode(self.import_file)
    #             data_file = io.StringIO(csv_data.decode("utf-8"))
    #             data_file.seek(0)
    #             csv_reader = csv.DictReader(data_file, delimiter=',')

    #         except:
    #             raise Warning(_("Invalid file!"))

    #         product = self.env['product.product']
    #         mrp_bom = self.env['mrp.bom']
    #         component_product = self.env['product.product']
    #         tax = self.env['account.tax']
    #         product_name = self.env['product.template']
    #         uom = self.env['uom.uom']
    #         lst =[]
    #         bom_operations = []
    #         bom_lines = [] 
    #         bom = None
    #         bom_data = {}
    #         product_template = None
    #         # Initialize collections and variables
    #         # Initialize lists to collect BoM lines and operations

    #         # Track components and operations for the current main product
    #         current_main_product = None

    #         for line in csv_reader:

    #             if self.bom_type == 'normal':
    #                 type = 'normal'

    #             if self.bom_type == 'phantom':
    #                 type = 'phantom'

    #             if line.get('Main Product'):

    #                 product = product.search([('name', '=', line.get('Main Product'))])
    #                 if not product:
    #                     product = product.create({
    #                         'name': line.get('Product'),
    #                     })
    #                 if len(product) > 1:
    #                     continue
    #                 product_name = product.product_tmpl_id
    #                 partner_count = product.sudo().search_count([('name', '=', line.get('Main Product'))])
    #                 lst.append(partner_count)

    #             if line.get('BoM Lines/Component'):
    #                 component_product = product.search([('name', '=', line.get('BoM Lines/Component'))])
    #                 if not component_product:
    #                     component_product = product.create({'name': line.get('BoM Lines/Component')})

    #             if not component_product or not component_product.id:
    #                 raise Warning(_("Component product not found or could not be created for '%s'.") % line.get('BoM Lines/Component'))

    #             if line.get('UOM'):
    #                 uom = uom.search([('name', '=', line.get('UOM'))])
    #                 if not uom:
    #                     uom = uom.create({
    #                         'name': line.get('UOM'),
    #                     })
    #             if line.get('Operations/Work Center'):
    #                 work_center = self.env['mrp.workcenter'].search([('name', '=', line.get('Operations/Work Center'))])
    #                 if not work_center:
    #                     raise Warning(_("Work Center '%s' not found.") % line.get('Operations/Work Center'))

    #             if line.get('Operations/Select from Existing Operations/Display Name'):
    #                 operation = self.env['mrp.routing.workcenter'].search([
    #                     ('name', '=', line.get('Operations/Select from Existing Operations/Display Name')),
    #                     ('workcenter_id', '=', work_center.id)
    #                 ])

    #             if not operation:
    #                 raise Warning(_("Operation '%s' not found for Work Center '%s'.") % (line.get('Operations/Select from Existing Operations/Display Name'), line.get('Operations/Work Center')))

    #             operation_line_vals = {
    #                 'workcenter_id': work_center.id,
    #                 'exist_workcenter_id': operation.id,
    #                 'name': line.get('Operations/Select from Existing Operations/Display Name'),
    #                 # Add any additional fields here based on the CSV and model requirements
    #             }

    #             # Append this operation to the list
    #             bom_operations.append((0, 0, operation_line_vals))

    #             bom_line_vals = {
    #                 'product_id': component_product.id,
    #                 'product_qty': line.get('Material Product Qty'),
    #                 'product_uom_id': uom.id,
    #                 }
    #             if not bom:
    #                 bom = mrp_bom.search([('product_tmpl_id', '=', product_name.id)], limit=1)
    #                 if not bom:
    #                     mrp_bom = mrp_bom.create({                    
    #                         'product_tmpl_id': product_name.id,
    #                         'product_uom_id': uom.id,
    #                         'product_qty': line.get('Main Product Qty') ,
    #                         'type':type,
    #                         'code':line.get('Reference'),
    #                         'bom_line_ids': [(0, 0, bom_line_vals)],
    #                         'operation_ids': bom_operations,

    #                     })
    #             bom.write({'bom_line_ids': [(0, 0, bom_line_vals)]})
    #         get_count=0
    #         for rec in lst:
    #             get_count = get_count+rec
                
    #         model = self.env.context.get('active_model')
    #         if model == 'custom.dashboard':
    #            vendor_info = self.env['custom.dashboard'].sudo().search([['name','=','Bill Of Material']])
    #            if vendor_info.count == 0:
    #               vendor_info.count = get_count
    #            else:
    #               vendor_info.count += get_count
               


    #     elif self.file_option == 'xls':
    #         fp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    #         fp.write(binascii.a2b_base64(self.import_file))
    #         fp.seek(0)
    #         workbook = xlrd.open_workbook(fp.name)
    #         sheet = workbook.sheet_by_index(0)
    #         keys = sheet.row_values(0)
    #         xls_reader = [sheet.row_values(i) for i in range(1, sheet.nrows)]
           

    #         product = self.env['product.product']
    #         mrp_bom = self.env['mrp.bom']
    #         tax = self.env['account.tax']
    #         product_name = self.env['product.template']
    #         uom = self.env['uom.uom']
    #         lst =[]
           

    #         for row in xls_reader:
    #             line = dict(zip(keys, row))
                

    #             if self.bom_type == 'normal':
    #                 type = 'normal'

    #             if self.bom_type == 'phantom':
    #                 type = 'phantom'

    #             if line.get('Main Product'):

    #                 product = product.search([('name', '=', line.get('Main Product'))])
    #                 if not product:
    #                     product = product.create({
    #                         'name': line.get('Product'),
    #                     })
    #                 partner_count = product.sudo().search_count([('name', '=', line.get('Main Product'))])
    #                 lst.append(partner_count)

    #             if line.get('Material Product'):

    #                 product_name = product_name.search([('name', '=', line.get('Material Product'))])
    #                 if not product_name:
    #                     product_name = product_name.create({
    #                         'name': line.get('Material Product'),
    #                     })

    #             if line.get('UOM'):
    #                 uom = uom.search([('name', '=', line.get('UOM'))])
    #                 if not uom:
    #                     uom = uom.create({
    #                         'name': line.get('UOM'),
    #                     })
                
    #             mrp_bom = mrp_bom.create({
    #                 'product_id': product.id,
    #                 'product_tmpl_id': product_name.id,
    #                 'product_uom_id': uom.id,
    #                 'product_qty': line.get('Main Product Qty') ,
    #                 'type':type,
    #                 'code':line.get('Reference'),

    #             })
    #         get_count=0
    #         for rec in lst:
    #             get_count = get_count+rec
                
    #         model = self.env.context.get('active_model')
    #         if model == 'custom.dashboard':
    #            vendor_info = self.env['custom.dashboard'].sudo().search([['name','=','Bill Of Material']])
    #            if vendor_info.count == 0:
    #               vendor_info.count = get_count
    #            else:
    #               vendor_info.count += get_count

          

    #     else:
    #         raise Warning(_("Invalid file!"))
