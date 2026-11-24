# -*- coding: utf-8 -*-
{
    "name": "EF Zebra Labels - Sales",
    "version": "14.0.2.0.0",
    "summary": "Customer label templates for sale order lines (starter set: INT505, CRE500, CAR635, ECO515, ECO525, SHE570)",
    "author": "Your Team",
    "license": "LGPL-3",
    "depends": ["ef_zebra_labels", "ef_sales"],
    "data": [
        "views/sale_label_views.xml",
        "data/label_templates.xml",
    ],
    "installable": True,
    "application": False,
}
