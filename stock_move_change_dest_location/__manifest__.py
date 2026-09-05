{
    "name": "Stock Move Change Destination Location",
    "summary": """
        This module allows you to change the destination location of stock moves
        from the picking
    """,
    "version": "14.0.1.0.0",
    "license": "AGPL-3",
    "author": "ATC ONLINE LLP",
    "depends": ["stock"],
    "data": [
        "security/ir.model.access.csv",
        "wizards/stock_move_change_dest_location_wizard.xml",
        "views/stock_picking_view.xml",
    ],
}
