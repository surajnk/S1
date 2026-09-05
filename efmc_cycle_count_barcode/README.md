# efmc_cycle_count_barcode

## Purpose

Thin customization module that changes the barcode scan behaviour of
`wiz.stock.barcodes.read.inventory` **only when** the inventory adjustment
is linked to a cycle count (`inventory_id.cycle_count_id` is set).

All normal inventory adjustments are completely unaffected.

## Scan flow (cycle count mode)

```
1. Scan location barcode  →  location locked for this session
2. Scan roll/lot barcode  →  product auto-resolved from lot, qty=1 written
3. Repeat step 2 for every roll present at that location
4. Scan a different location barcode to move to next bay
5. Validate the inventory adjustment when done
```

## What changes vs standard mode

| Behaviour              | Standard mode       | Cycle count mode          |
|------------------------|---------------------|---------------------------|
| Product scan required  | Yes                 | **No** — resolved from lot|
| Lot scan required      | After product       | **First scan** (after loc)|
| Qty input              | Manual              | **Auto = 1** (presence)   |
| Location locked        | Can change freely   | **Stays set** after scan  |
| After each scan        | Clears all fields   | **Keeps location**        |

## How the gate works

`_is_cycle_count_session()` checks:
```python
bool(self.inventory_id and self.inventory_id.cycle_count_id)
```
Every overridden method calls this first and falls through to `super()` if False.

## Dependencies

- `stock_barcodes` (OCA)
- `stock_cycle_count` (OCA)

## Setup checklist

1. Install this module
2. In **Settings → Companies**:
   - ✅ Auto Start Inventory from Cycle Count
   - Counted Quantities = **Zero** (blind count)
3. Ensure all storage locations have a **Barcode** value set
4. Ensure all rolls/lots have their lot name matching the printed barcode

## Notes

- The `_is_cycle_count_session()` guard is the single point of control.
  If you need to disable cycle count mode for a specific inventory, simply
  clear the `cycle_count_id` field on that inventory adjustment.
- If a lot barcode is not found (new roll not in system), the scanner
  plays the error sound and shows "Roll not found". The operator must
  first create the lot in Odoo before it can be scanned.
