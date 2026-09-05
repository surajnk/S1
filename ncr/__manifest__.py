# -*- coding: utf-8 -*-

{
    'name': 'NCR',
    'version': '14.0.4.1.0',
    'category': 'mrp',
    'summary': 'NCR in MRP and Purchase',
    'sequence': '1',
    'author': 'ATC',
    'license': 'LGPL-3',
    'depends': ['base','web_domain_field','stock','mrp','purchase','ef_product','mrp_enhancement'],
    'demo': [],
    'data': [
        'security/ir.model.access.csv',
        'views/res_nrc_view.xml',
        'views/defect_master_view.xml',
        'views/report_ncr.xml',
        'views/deposition_code_view.xml',
        'security/security.xml',
        'data/sequence.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'qweb': [],
}
