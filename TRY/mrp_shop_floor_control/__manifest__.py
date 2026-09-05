# -*- coding: utf-8 -*-
# Copyright (c) Open Value All Rights Reserved

{
    'name': 'MRP Shop Floor Control',
    'summary': 'MRP Shop Floor Control',
    'version': '14.0.3.0.',
    'category': 'Manufacturing',
    'website': 'www.openvalue.cloud',
    'author': "OpenValue",
    'support': 'info@openvalue.cloud',
    'license': "Other proprietary",
    'price': 600.00,
    'currency': 'EUR',
    'depends': [
            'mrp',
            'openvalue_warehouse_calendar',
            'ef_mrp',
            'stock',
            'mrp_confirmed_date_base'
    ],
    'demo': [],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_floating_times_views.xml',
        'views/mrp_workcenter_views.xml',
        'views/mrp_routing_workcenter_views.xml',
        'views/mrp_workorder_views.xml',
        'views/mrp_workcenter_capacity_views.xml',
        'wizards/mrp_confirmation_views.xml',
        'wizards/mrp_capacity_check_views.xml',
        'views/mrp_production_views.xml',
        'views/mrp_workcenter_capacity_report_view.xml',
        'wizards/wc_report_change_date_wiz_view.xml',
        'wizards/mrp_workcenter_report.xml',
        "views/mrp_workcenter_productivity_view.xml",
        "views/mrp_production_roll_view.xml",
        'views/mrp_workorder_report.xml',
        'report/mrp_workorder_report.xml',
        #'views/mrp_confirmed_date_suggestion_wizard_views.xml',
        'views/mrp_production_roll_views.xml',
    ],
    "qweb": [
        "static/src/xml/qweb_templates.xml",
        "static/src/xml/qweb_workorder.xml"
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
    'images': ['static/description/banner.png'],
}
