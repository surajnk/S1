# -*- coding: utf-8 -*-
{
    'name': "inherit_uom",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','uom'],

    # always loaded
    'data': [
        'views/inherit_uom_view.xml',

    ],
}
