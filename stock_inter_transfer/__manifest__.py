# -*- coding: utf-8 -*-
{
    'name': "Inter Warehouse Transfer",
    'version': '14.0.1.0.0',
    'summary': 'Inter Warehouse Transfer',
    'description': """Transfer stock from one warehouse to another warehouse.""",
    'depends': ['stock'],
    'data': [
        "data/ir_sequence.xml",
        "security/ir.model.access.csv",
        "views/stock_transfer_view.xml",
        "views/stock_picking_view.xml",
        "views/res_config_settings_view.xml"
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
