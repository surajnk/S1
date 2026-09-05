# Copyright 2024 EFMC
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class WizStockBarcodesReadInventory(models.TransientModel):
    _inherit = "wiz.stock.barcodes.read.inventory"

    # -------------------------------------------------------------------------
    # Helper: are we in cycle count mode?
    # -------------------------------------------------------------------------

    def _is_cycle_count_session(self):
        """
        Returns True only when the linked inventory adjustment was created
        from a cycle count. This is the single gate that controls all
        custom behaviour in this module.
        """
        return bool(
            self.inventory_id and self.inventory_id.cycle_count_id
        )

    # -------------------------------------------------------------------------
    # Step display: in cycle count mode show simpler instructions
    # -------------------------------------------------------------------------

    @api.onchange("step")
    def action_show_step(self):
        if not self._is_cycle_count_session():
            return super().action_show_step()

        # Cycle count mode: just two steps
        #   step 0 → waiting for location
        #   step 1 → waiting for roll/lot barcode
        if not self.location_id:
            self._set_messagge_info("info", _("Scan location barcode"))
        else:
            self._set_messagge_info("info", _("Scan roll / lot barcode"))

    # -------------------------------------------------------------------------
    # Core barcode processor override
    # -------------------------------------------------------------------------

    def process_barcode(self, barcode):
        """
        In cycle count mode:
          - Any barcode is first tried as a location.
          - If not a location, tried as a lot (roll).
          - Product scan step is skipped entirely.
          - Quantity is always forced to 1 (presence = 1).

        Normal mode: delegate to super() unchanged.
        """
        if not self._is_cycle_count_session():
            return super().process_barcode(barcode)

        self._set_messagge_info("success", _("OK"))

        # --- Step 1: try as location ---
        location = self.env["stock.location"].search(
            [("barcode", "=", barcode)], limit=1
        )
        if location:
            self.location_id = location
            self._set_messagge_info(
                "success", _("Location: %s") % location.display_name
            )
            self.action_show_step()
            self.play_sounds(True)
            return True

        # --- Must have a location before scanning rolls ---
        if not self.location_id:
            self._set_messagge_info("info", _("Scan location barcode first"))
            self.play_sounds(False)
            return False

        # --- Step 2: try as lot / roll barcode ---
        return self._process_cycle_count_lot(barcode)

    def _process_cycle_count_lot(self, barcode):
        """
        Look up the lot by barcode name (no product filter needed — the lot
        carries its own product_id).  Auto-resolve product, force qty=1,
        and immediately write the inventory line.
        """
        if not self.env.user.has_group("stock.group_production_lot"):
            self._set_messagge_info(
                "not_found", _("User has no lot tracking access")
            )
            self.play_sounds(False)
            return False

        lot = self.env["stock.production.lot"].search(
            [
                ("name", "=", barcode),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )

        if not lot:
            self._set_messagge_info(
                "not_found", _("Roll / Lot '%s' not found") % barcode
            )
            self.play_sounds(False)
            return False

        # Auto-resolve product from lot — no product scan needed
        self.product_id = lot.product_id
        self.product_uom_id = lot.product_id.uom_id
        self.lot_id = lot
        # Presence check: qty is always 1 (roll is either here or not)
        self.product_qty = 1.0

        _logger.info(
            "Cycle count scan: lot=%s product=%s location=%s qty=1",
            lot.name,
            lot.product_id.display_name,
            self.location_id.display_name,
        )

        # Write inventory line immediately — no manual confirm needed
        result = self.action_confirm()
        if result:
            self._set_messagge_info(
                "success",
                _("Roll %s (%s) recorded") % (lot.name, lot.product_id.display_name),
            )
            # Clear lot/product ready for next roll scan
            # location stays locked until operator rescans a different location
            self._cycle_count_clean_after_scan()
        self.play_sounds(bool(result))
        return bool(result)

    def _cycle_count_clean_after_scan(self):
        """
        After each roll scan: clear product/lot fields only.
        Location stays set so operator can keep scanning rolls in same bay.
        """
        self.product_id = False
        self.lot_id = False
        self.lot_name = False
        self.product_qty = 0.0
        self.packaging_qty = 0.0

    # -------------------------------------------------------------------------
    # check_done_conditions: relax lot requirement check in cycle count mode
    # (product is always resolved from lot so both arrive together)
    # -------------------------------------------------------------------------

    def check_done_conditions(self):
        if not self._is_cycle_count_session():
            return super().check_done_conditions()

        # In cycle count mode we only need location + lot + product
        if not self.location_id:
            self._set_messagge_info("info", _("Waiting location"))
            return False
        if not self.product_id:
            self._set_messagge_info("info", _("Waiting roll / lot barcode"))
            return False
        if not self.lot_id:
            self._set_messagge_info("info", _("Waiting lot"))
            return False
        if not self.product_qty:
            self.product_qty = 1.0
        return True

    # -------------------------------------------------------------------------
    # check_lot_contidion: always True in cycle count mode
    # (lot is resolved by our custom path before check_done_conditions runs)
    # -------------------------------------------------------------------------

    def check_lot_contidion(self):
        if not self._is_cycle_count_session():
            return super().check_lot_contidion()
        return True

    # -------------------------------------------------------------------------
    # action_clean_values: in cycle count keep location, clear rest
    # -------------------------------------------------------------------------

    def action_clean_values(self):
        if not self._is_cycle_count_session():
            return super().action_clean_values()
        self._cycle_count_clean_after_scan()
