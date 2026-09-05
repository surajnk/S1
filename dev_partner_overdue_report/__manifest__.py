# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################

{
    'name': 'Partner Overdue & Breakdown Aging Report odoo',
    'version': '14.0.1.0',
    'sequence':1,
    'category': 'Generic Modules/Accounting',
    'description': """
        Partner Overdue & Breakdown Aging Report odoo
         Customer/supplier overdue aging repor
         Overdue Aging Based on Invoice Date / Invoice Due Date
         Option to filter By All / specif Selected Partner Overdue report 
         Report Print in Simple / Break Down format in PDF or EXCEL
         
        Odoo overdue report 
        Odoo customer overdue report 
        Odoo supplier overdue report
        odoo customer/supplier overdue report 
        odoo customer aging
        odoo supplier aging
        partner receivable aging
        partner payable aging  
        odoo receivable aging
        odoo payable aging
        due date overdue report
        Invoice date overdue report
        odoo due date overdue report
        Odoo Invoice date overdue report
        odoo partner invoice breakdown report
        odoo Supplier invoice breakdown report
        odoo customer invoice breakdown report
        partner breakdown by due date 
        partner breakdown by Invoice date 

    """,
    'summary':'Odoo app will Print Partner overdue Report and Invoice Breakdown Aging Report, overdue report , Breakdown Aging Report,due date overdue report, partner invoice breakdown report,customer aging,supplier aging, customer statement, partner overdue',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/dev_partner_overdue_view.xml',
        'views/overdue_header.xml',
        'views/partner_overdue_template.xml',
        'views/partner_overdue_break_template.xml',
        'views/report_menu.xml',
    ],
    'demo': [],
    'test': [],
    'css': [],
    'qweb': [],
    'js': [],
    'images': ['images/main_screenshot.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    
    #author and support Details
    'author': 'DevIntelle Consulting Service Pvt.Ltd',
    'website': 'http://www.devintellecs.com',    
    'maintainer': 'DevIntelle Consulting Service Pvt.Ltd', 
    'support': 'devintelle@gmail.com',
    'price':35.0,
    'currency':'EUR',
    #'live_test_url':'https://youtu.be/A5kEBboAh_k',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
