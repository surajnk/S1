# -*- coding: utf-8 -*-
# Copyright (c) OpenValue All Rights Reserved

{
    'name': 'Stock Transfer Interwarehouses',
    'summary': 'Stock Transfer Interwarehouses',
    'version': '14.0.1.0.0',
    'category': 'Inventory/Inventory',
    'website': 'www.openvalue.cloud',
    'author': 'OpenValue',
    'support': 'info@openvalue.cloud',
    'license': 'Other proprietary',
    'price': 150.00,
    'currency': 'EUR',
    'depends': [
        'stock','ef_product','report_xlsx'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/stock_transfer_sequence.xml',
        'data/template_mail.xml',
        'views/stock_transfer_views.xml',
        'views/stock_transfer_line_views.xml',
        'wizard/product_account_report_view.xml'
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}
