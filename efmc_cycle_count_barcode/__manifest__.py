# Copyright 2024 EFMC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "EFMC Cycle Count Barcode",
    "version": "14.0.1.0.0",
    "category": "Inventory",
    "summary": "Lot-only barcode scanning for cycle count inventory adjustments",
    "description": """
        When an inventory adjustment is linked to a cycle count (cycle_count_id is set),
        the barcode scan mode changes to:
          1. Scan location barcode  → sets location
          2. Scan lot/roll barcode  → auto-resolves product from lot, sets qty=1
          No product barcode scan required. No qty input required.
        Normal inventory adjustments (no cycle_count_id) are unaffected.
    """,
    "author": "EFMC",
    "depends": [
        "stock_barcodes",
        "stock_cycle_count",
    ],
    "data": [
        "views/stock_barcodes_read_inventory_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
