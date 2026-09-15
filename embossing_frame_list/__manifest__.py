# -*- coding: utf-8 -*-

{
    'name': 'Embossing Frame List',
    'summary': 'Live list of embossing frames with their current pattern and MO/SO',
    'version': '14.0.1.0.0',
    'category': 'Manufacturing',
    'author': 'OpenValue',
    'license': 'Other proprietary',
    'depends': [
        'mrp',
        'sale',
        'ef_mrp',
        'ef_product',
        'mrp_shop_floor_control',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_embossing_frame_list_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
