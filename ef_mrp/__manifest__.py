{
    'name': 'MRP Extension - EF',
    'summary': """
        MRP Extension - EF 
        """,
    'description': """
        MRP Extension - EF
    """,
    'category': 'MRP',
    'author': 'ATC ONLINE LLP',
    'company': 'ATC ONLINE LLP',
    'maintainer': 'Suraj',
    'version': '14.0.0.1',
    'depends': ['sale_management','ef_product','mrp','resource'],
    'data': [
        'security/ir.model.access.csv',
        # 'views/product_commodity_code_view.xml',
        # 'views/product_item_group_view.xml',
        'views/ef_mrp_view.xml',
        'views/mrp_bom_view.xml',
        'views/mrp_component_lines_views.xml',
        'wizard/manufacture_workorder_filter_wizard.xml'
        # 'views/product_break_codes_view.xml',
        # 'views/labor_items_view.xml',
        # 'views/price_group_view.xml',
        # 'views/product_view.xml',
        # 'views/class_code_view.xml',
        # 'views/extra_knives.xml',
        # 'data/ef_product_data.xml'
    ],
    'qweb': [
    ],
    'demo': [
        
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
