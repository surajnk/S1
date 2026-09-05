# -*- coding: utf-8 -*-
{
    "name": "EF Zebra Print (Raw ZPL via CUPS/LPD)",
    "version": "14.0.1.0.0",
    "summary": "Register Zebra printers and send ZPL directly to CUPS/LPD queues",
    "author": "Your Team",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/zebra_printer_views.xml",
    ],
    "installable": True,
    "application": False,
}
