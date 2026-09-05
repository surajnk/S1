# -*- coding: utf-8 -*-
{
    'name': 'MRP Workorder Notifications',
    'version': '14.0.1.0.0',
    'author': 'Your Company',
    'depends': ['mrp_shop_floor_control', 'mail'],
    'data': [
        'data/mrp_workorder_server_actions.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
}
