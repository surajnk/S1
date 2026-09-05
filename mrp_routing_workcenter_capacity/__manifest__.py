# Copyright 2021 Alfredo de la Fuente - AvanzOSC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "MRP Routing Workcenter Capacity",
    "version": '14.0.1.0.0',
    "author": "Avanzosc",
    "license": "AGPL-3",
    "category": "Manufacturing/Manufacturing",
    "depends": [
        "mrp","ef_product", 'mrp_shop_floor_control'
    ],
    "data": [
        'security/ir.model.access.csv',
        'views/mrp_routing_workcenter_views.xml',
        'views/mrp_production_workorder_view.xml',
        'reports/mrp_workcenter_productivity_label_view.xml'
    ],
    "installable": True,
}
