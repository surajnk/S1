# -*- coding: utf-8 -*-
{
	'name': 'Sticky Pivot View',

	'summary': """
Enhance the default Odoo Pivot View by sticking the Pivot View Header and its first Column.
""",

	'description': """
Enhance the default Odoo Pivot View by sticking the Pivot View Header and its first Column.
        Pivot View
        Sticky Pivot View
        Odoo Sticky Pivot View
        Odoo Pivot View
        Web List View Sticky Header
        Odoo Sticky Header
        Pivot View Sticky Header
        Sticky Header
        Sticky Pivot View Header
        Sticky Pivot View Column
        Freeze Pivot View
""",

	'author': 'Suraj',


	'license': 'OPL-1',


	'category': 'Tools',

	'version': '14.0.1.0.2',


	'images': ['static/description/ks_sticky_pivot_view.gif'],

	'depends': ['base', 'web', 'base_setup'],

	'qweb': ['static/src/xml/ks_pivot_view.xml'],

	'data': ['data/ks_data_ir_config_parameter.xml', 'views/ks_assets.xml', 'views/ks_inherited_res_config.xml'],

	'uninstall_hook': 'uninstall_hook',
}
