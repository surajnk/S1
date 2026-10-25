# -*- coding: utf-8 -*-
{
    "name": "EF Zebra Labels",
    "version": "14.0.1.0.0",
    "summary": "Customer label ZPL templates, kept as .zpl files per model, printed through ef_zebra_print",
    "author": "Your Team",
    "license": "LGPL-3",
    "depends": ["ef_zebra_print", "ef_sales"],
    "data": [
        "wizard/zebra_label_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
