# -*- coding: utf-8 -*-
{
    'name': 'Invoice Latest Delivery Date',
    'version': '16.0.1.0.0',
    'summary': 'Show latest delivery date on customer invoices',
    'category': 'Sales',
    'depends': ['sale_stock', 'account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
