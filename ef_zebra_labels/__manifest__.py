# -*- coding: utf-8 -*-
{
    "name": "EF Zebra Labels",
    "version": "14.0.2.0.0",
    "summary": "Label templates (ZPL + field mapping) for any model, per customer, printed through ef_zebra_print",
    "author": "Your Team",
    "license": "LGPL-3",
    "depends": ["ef_zebra_print"],
    "data": [
        "security/ir.model.access.csv",
        "views/zebra_label_template_views.xml",
        "wizard/zebra_label_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
