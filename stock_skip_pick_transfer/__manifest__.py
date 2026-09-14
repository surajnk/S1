{
    "name": "Stock Skip Pick Transfer",
    "summary": """
        Optionally skip a pending Pick transfer when validating a source
        transfer (e.g. Store Finished Product) whose stock can satisfy it.
    """,
    "description": """
        On operation types flagged "Offer to Skip Pick on Validate", validating
        a transfer whose product(s) can satisfy a pending Pick transfer in the
        same warehouse opens a confirmation wizard. The user chooses whether to
        skip the Pick transfer(s) and send the stock straight through to
        Pack/Delivery, or to keep the normal flow.

        Skipped Pick transfers are force-completed for only the quantity the
        source transfer actually processed (never more), tracing the same
        lot(s) when the product is lot/serial tracked, and any unmet demand is
        left as a normal backorder.
    """,
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "category": "Inventory",
    "author": "ATC ONLINE LLP",
    "depends": ["stock", "mrp"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_picking_type_views.xml",
        "wizards/stock_skip_pick_wizard_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
