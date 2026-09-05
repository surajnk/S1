# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "Merge Manufacturing Orders",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "license": "OPL-1",
    "support": "support@softhealer.com",
    "category": "Manufacturing",
    "summary": "Merge MRP, Merge MRP Order, Merge MRP Orders, Merge Manufacturing Order, Append MRP Order, Combine MRP, Combine MRP Order, Combine MRP Orders, Combine Manufacturing Orders, Manage Manufacturing Orders Odoo",
    "description": """This module useful to merge manufacturing orders. Some times required to make a single order from the multiple MRP orders. You can merge MRP orders which are only in the draft/ confirmed/ in-progress state. Your MRP orders must have the same product/bill of materials for merge orders. You can merge manufacturing orders with many options. Merge MRP orders notification comes into the chatter!""",
    "version": "14.0.6",
    "depends": [
        "mrp",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_setting.xml",
        "wizard/merge_mrp_order.xml",
    ],
    "images": ["static/description/background.png", ],
    "auto_install": False,
    "application": True,
    "installable": True,
    "price": 25,
    "currency": "EUR"
}
