{
    "name": "MRP Enhancement points",
    "author": "Dhvanil",
    "website": "",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "summary": "",
    "description": """
Set Mid Point Scheduling functionality on manufacturing wo lines
""",
    'version': '14.0.1.0.2',
    "depends": [
        "mrp", "stock", "sale_stock",
        "mrp_shop_floor_control", "eq_invoice_from_picking",
        "mrp_routing_workcenter_capacity", "ef_mrp", "mrp_mto_analytic","barcodes"
    ],
    "data": [
        'security/security.xml',
        "views/mrp_production_views.xml",
        "views/stock_move_line_views.xml",
        "views/stock_picking_views.xml",
        "views/mrp_routing_workcenter_views.xml",
        "views/mrp_workcenter_productivity_view.xml",
        "views/mrp_workcenter_capacity_views.xml",
        "views/sale_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/asset.xml",
        "views/res_config_settings_views.xml",
        "views/mrp_backorder_confirmation_views.xml",
        #"reports/mrp_wo_scheduling_views.xml",
        "wizard/roll_line_wiazrd_views.xml",
        "wizard/extra_time_views.xml",
        "data/ir_cron_data.xml",
        "data/server_actions.xml",
        "wizard/roll_transfer_wizard_views.xml",
        'security/ir.model.access.csv',
    ],
    "images": [],
    "auto_install": False,
    "application": True,
    "installable": True,
}
# -*- coding: utf-8 -*-
