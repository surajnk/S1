{
    'name': 'EF - Purchase',
    'summary': """
        EF - Purchase 
        """,
    'description': """
        EF - Purchase

        Version 14.0.0.1 - Customization in Purchase for EF.
    """,
    'category': 'Purchase',
    'author': 'Vaikalp Tech Ventures LLP',
    'company': 'Vaikalp Tech Ventures LLP',
    'maintainer': 'Jignesh Mehta',
    'website': 'https://www.vaikalp.com',
    'version': '14.0.0.1',
    'depends': ['purchase', 'custom_partner', 'sale_management', 'ef_product'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_view.xml',
        'views/sale_view.xml',
        'views/purchase_product_break_code_view.xml',
        'views/product_view.xml',
        'views/move_view.xml',
        'views/res_partner_view.xml',
        'views/purchase_order_line.xml',
        'report/purchase_report.xml',
    ],
    'qweb': [

    ],
    'demo': [

    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
