# -*- coding: utf-8 -*-

{
    'name': 'BoM Components Lines',
    'version': '13.0.1.0.0',
    'author': 'PPTS [India] Pvt.Ltd.',
    'website': 'https://www.pptssolutions.com',
    'category': 'Manufacturing',
    'description': """Standalone list view for Bill of Materials components""",
    'depends': ['mrp', 'ef_mrp'],
    'license': 'LGPL-3',
    'data': [
        'views/mrp_bom_line_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
