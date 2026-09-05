# -*- coding: utf-8 -*-
# Copyright (c) Open Value All Rights Reserved

{
    'name': 'MRP Analytic MTO',
    'summary': 'MRP Analytic MTO',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'website': 'www.openvalue.cloud',
    'author': "OpenValue",
    'support': 'info@openvalue.cloud',
    'license': "Other proprietary",
    'price': 300.00,
    'currency': 'EUR',
    'depends': [
        'sale_stock',
        'purchase_stock',
        'sale_purchase',
        'sale_mrp',
        'purchase_mrp',
        'mrp_shop_floor_control',
        'mrp_product_costing',
        'mrp_confirmed_date_base'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/product_views.xml',
        'views/sale_order_views.xml',
        'views/stock_move_views.xml',
        'wizards/mrp_mto_supply_chain_views.xml',
        ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}
