{
    'name': 'Product Extension - EF',
    'summary': """
        Product Extention - EF 
        """,
    'description': """
        Product Extention - EF

        Version 14.0.0.1 - Add Product Master data. Add fields in Product form view.
    """,
    'category': 'Product',
    'author': 'ATC ONLINE LLP',
    'company': 'ATC ONLINE LLP',
    'maintainer': 'Suraj',
    'version': '14.0.0.1',
    'depends': ['sale_management','mrp','purchase','branch','stock',],
    'data': [
        'security/ir.model.access.csv',
        'views/product_commodity_code_view.xml',
        'views/product_item_group_view.xml',
        'views/product_harmonized_codes_view.xml',
        'views/product_break_codes_view.xml',
        'views/labor_items_view.xml',
        'views/price_group_view.xml',
        'views/product_view.xml',
        'views/extra_knives.xml',
        'views/class_code_view.xml',
        'views/product_novaflow.xml',
        'views/product_embossing.xml',
        'data/ef_product_data.xml',
        'security/security_view.xml',
        'views/on_order_wizard_view.xml',
    ],
    'qweb': [
        
    ],
    'demo': [
        
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
