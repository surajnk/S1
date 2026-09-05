# -*- coding: utf-8 -*-
# Copyright (c) Open Value All Rights Reserved

{
'name': 'MRP Product Costing',
 'summary': 'MRP Product Costing',
 'version': '14.0.1.1.0',
 'category': 'Manufacturing',
  "website": 'www.openvalue.cloud',
  'author': "Open Value",
  'support': 'info@openvalue.cloud',
  'license': "Other proprietary",
  'price': 400.00,
  'currency': 'EUR',
    "depends": [
        'stock_account',
        'purchase_stock',
        'mrp_account',
        'analytic',
        'mrp_shop_floor_control',
    ],
    "data": [
        'security/ir.model.access.csv',
        'views/account_move_line_views.xml',
        'views/account_analytic_line_views.xml',
        'views/mrp_product_costing_parameters.xml',
        'views/mrp_workcenter_views.xml',
        'views/mrp_bom_views.xml',
        'views/mrp_production_views.xml',
        'views/mrp_product_costing_views.xml',
    ],
  'application': False,
  'installable': True,
  'auto_install': False,
  'images': ['static/description/banner.png'],
}
