{
    'name': 'Stock Extension - EF',
    'summary': """
        Stock Extension - EF 
        """,
    'description': """
        Stock Extension - EF
    """,
    'category': 'Stock',
    'author': 'ATC ONLINE LLP',
    'company': 'ATC ONLINE LLP',
    'maintainer': 'Suraj',
    'version': '14.0.0.1',
    'depends': ['sale_management', 'ef_product', 'mrp', 'stock', 'branch','custom_partner'],
    'data': [
        'security/ir.model.access.csv',
        'views/sequence_view.xml',
        'views/nmfc_density_class_view.xml',
        'reports/report_bill_of_leading.xml',
        'reports/barcode_report_templates.xml',
        'views/report_view.xml',
        'views/product_replenish_view.xml',
        'views/stock_picking_view.xml',
        'views/ef_stock_view.xml',
        'wizard/bill_of_leading_wiz_view.xml',
        'security/tow_security.xml',
        'views/product_category_views.xml',
        'data/server_actions.xml',
    ],
    'qweb': [],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
}
