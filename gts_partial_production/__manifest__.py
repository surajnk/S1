# -*- coding: utf-8 -*-

{
    'name': 'Gts Partial Production | Record Partial Manufactured Products in Odoo',
    'version': '13.0.0.1',
    'sequence': 1,
    'author': 'Geo Technosoft',
    'website' : 'http://www.geotechnosoft.com',
    'category': 'Manufacturing',
    'support': 'info@geotechnosoft.com',
    'depends' : ['base', 'mrp', 'mrp_enhancement', 'sale_stock', 'ef_sales'],
    'summary': '''
        Manufacturing partial production from MO order and also update the stock the same time ''',
    'description': """
         This module allows partial production from MO order and also update the stock the same time
    partial manufacturing short production record partial production record 
    Produce partially record partially in odoo
    update partial production mid of manufacturing incomplete production incomplete manufacturing
    update partially produced stock in odoo
    partially update stock produced partially update stock production
    partial Manufacturing production
    """,
    'data': [
        'security/ir.model.access.csv',
        'wizard/mrp_produce_produce_view.xml',
        'views/mrp_production_view.xml',
        'views/mrp_workorder_view.xml',
        "views/mrp_workcenter_view.xml",
        "views/stock_picking_view.xml",
        "views/stock_quant_package_view.xml",
        "views/sale_order_view.xml",
        "report/report_package_barcode.xml",
    ],
    'images': [
        'static/description/banner.png',
    ],
    'price': 19.99,
    'currency': 'EUR',
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'application': True
}