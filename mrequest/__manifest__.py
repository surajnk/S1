# -*- coding: utf-8 -*-
{
    'name': "Material Request",
    'author': "Diana",
    'website': "https://www.odoopro365.com",
    "support": "support@odoopro365.com",
    "license": "OPL-1",
    'category': 'Operations/Purchase',
    'summary': """
        User can send material/product request to purchase departement""",

    'description': """
        User can request material/products from purchase departement
        Purchase departement can convert materail requisition to purchase order

    """,
    'version': '13.0.1',
    'depends': ['base', 'purchase', 'stock', 'project', 'mrp'],

    'application': True,
    'data': [
        'security/ir.model.access.csv',
        'security/mrequest_security.xml',
        'data/sequence.xml',
        'views/views.xml',
        'reports/material_request_report.xml',

    ],

    "images": ["static/description/background.png", ],
    "auto_install": False,
    'application': True,
    "installable": True,
    "price": 30,
    "currency": "EUR"
}
