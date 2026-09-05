{
    'name': 'Stock Conversion',
    'summary': """
        Stock Conversion
        """,
    'description': """
        Stock Conversion
    """,
    'category': 'Stock',
    'author': 'Vaikalp Tech Ventures LLP',
    'company': 'Vaikalp Tech Ventures LLP',
    'maintainer': 'Jignesh Mehta',
    'website': 'https://www.vaikalp.com',
    'version': '14.0.0.1',
    'depends': ['stock', 'ef_product'],
    'data': [
        'security/ir.model.access.csv',
        'security/stock_conversion_group.xml',
        'data/stock_conversion_seq.xml',
        'report/report_action_view.xml',
        'report/report_stock_conversion_view.xml',
        'views/stock_conversion_view.xml',
        'views/stock_inventory_view.xml',
        'wizard/stock_conversion_wiz_view.xml',
        'views/stock_picking_view.xml',
    ],
    'qweb': [

    ],
    'demo': [

    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
