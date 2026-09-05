{
    "name": "Manage Delivered Qty in Sale order line",
    "author": "Dhvanil",
    "website": "",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "summary": "",
    "description": """
Manage Delivered Qty in Sale order line
""",
    'version': '14.0.1.0.1',
    "depends": [
        'ef_sales', 'procurement_jit',
    ],
    "data": [
        # 'security/ir.model.access.csv',
        # 'security/security.xml',
        "views/sale_order_line_views.xml",
        "views/stock_move_views.xml",
    ],
    "images": [],
    "auto_install": False,
    "application": True,
    "installable": True,
}
