# -*- coding: utf-8 -*-
{
    "name": "MRP enhancement",
    "author": "Dhvanil",
    "website": "",
    "license": "LGPL-3",
    "category": "Manufacturing",
    "summary": "",
    "description": """MRP enhancement""",
    'version': '14.0.1.0.0',
    "depends": [
        "mrp","mrp_enhancement",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/mrp_enhancement_security.xml",
        "report/mrp_reports.xml",
        "report/mrp_workorder_custom_report.xml",
        "views/mrp_workorder_views.xml",
        "views/mrp_views.xml",
        "wizards/mrp_wo_report_wizard_views.xml",
    ],
    "images": [],
    "auto_install": False,
    "application": True,
    "installable": True,
}
