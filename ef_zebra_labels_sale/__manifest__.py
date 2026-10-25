# -*- coding: utf-8 -*-
{
    "name": "EF Zebra Labels - Sales",
    "version": "14.0.1.0.0",
    "summary": "Customer labels (INT505, CRE500, CAR635, ECO515, ECO525) printed from sale order lines",
    "author": "Your Team",
    "license": "LGPL-3",
    "depends": ["ef_zebra_labels", "ef_sales"],
    "data": [
        "views/sale_label_views.xml",
    ],
    "installable": True,
    "application": False,
}
