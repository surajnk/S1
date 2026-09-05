# -*- coding: utf-8 -*-
##############################################################################
#
#    Shinefy Technologies Pvt. Ltd.
#    Copyright (C) 2022 Shinefy Technologies.
#    Author: Shinefy Technologies
#    
#    For Module Support : shinefytech@gmail.com  or Skype : shinefytech@gmail.com
#
##############################################################################

{
    'name': 'Invoice Approval',
    'category': 'Accounting',
    'version': '14.0.1.2',
    'author' : "ShinefyTech",
    'maintainer' : "ShinefyTech",
    'description' : '''
          The application allows you to approve invoices through the setting of approvals.
    ''',
    'summary' : 'The application allows you to approve invoices through the setting of approvals.',
    'depends' : ['account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_view.xml',
        'views/acc_move_view.xml',
        'wizard/rej_wiz.xml'
    ],
    'live_test_url' :'https://youtu.be/8A_eIIc6rBU',
    'license': 'LGPL-3',
    'installable' : True,
    'auto_install' : False,
    'images' : ['static/description/Banner.gif'],
    'price': '10',
    'currency': "EUR", 
}
