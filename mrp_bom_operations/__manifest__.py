# -*- coding: utf-8 -*-

{
    'name': 'BoM Operations Lines',
    'version': '13.0.1.0.1',
    'author': 'PPTS [India] Pvt.Ltd.',
    'website': 'https://www.pptssolutions.com',
    'category': 'Manufacturing',
    'description': """Standalone list view for Bill of Materials operations""",
    'depends': ['mrp'],
    'license': 'LGPL-3',
    'data': [
        'views/mrp_bom_operation_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
