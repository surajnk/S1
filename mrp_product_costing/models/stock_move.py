# -*- coding: utf-8 -*-

from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.model
    def _prepare_account_move_line(self, qty, cost, credit_account_id, debit_account_id, description):
        # keep the original behaviour, but tag MO on lines
        res = super()._prepare_account_move_line(qty, cost, credit_account_id, debit_account_id, description)
        for line in res:
            # line is (move_line_name, move_line_vals?) typical Odoo structure from 12/13 implementations
            try:
                if self.production_id:
                    line[2]["manufacture_order_id"] = self.production_id.id
                elif self.raw_material_production_id:
                    line[2]["manufacture_order_id"] = self.raw_material_production_id.id
            except Exception:
                # safe: some Odoo versions have different tuple shapes; ignore tagging if fails
                pass
        return res

    def _is_fg_receipt(self):
        """
        Heuristic: FG receipt if this move belongs to MO and is leaving a production/WIP usage
        towards an internal stock location.
        """
        src_usage = getattr(self.location_id, 'usage', '')
        dst_usage = getattr(self.location_dest_id, 'usage', '')
        return bool(self.production_id) and (src_usage in ('production', 'internal')) and (dst_usage == 'internal')

    def _get_accounting_data_for_valuation(self):
        """
        Route valuation via the finished product category's single WIP account (if present).
        Logic (with fallbacks):
          - RM consumption (stock -> WIP):  Cr RM category / Dr Category WIP
          - WIP -> WIP (internal transfers): Cr Category WIP / Dr Category WIP (same account => net)
          - FG receipt (WIP -> internal stock): Cr Category valuation / Dr Category WIP
        Fallbacks:
          - If product.category has no WIP field, fall back to location valuation_in/out accounts
          - If still missing, keep super() accounts
        """
        journal_id, acc_src, acc_dest, acc_valuation = super()._get_accounting_data_for_valuation()
        self.ensure_one()

        # Category valuation (inventory) account (standard)
        categ_val = (self.product_id.categ_id.property_stock_valuation_account_id.id
                     if self.product_id.categ_id else False)

        # Determine the category that should provide the WIP account.
        # Prefer the finished product category whenever we are consuming raw
        # materials for a MO, otherwise fall back to the move product category.
        wip_categ = self.product_id.categ_id
        if self.raw_material_production_id and getattr(self.raw_material_production_id.product_id, 'categ_id', False):
            wip_categ = self.raw_material_production_id.product_id.categ_id or wip_categ
        elif self.production_id and getattr(self.production_id.product_id, 'categ_id', False):
            wip_categ = self.production_id.product_id.categ_id or wip_categ

        # make sure property fields are read in the move company to avoid cross-company
        # fallbacks that could yield the stock valuation account instead of the WIP one
        if wip_categ and hasattr(self, 'company_id') and self.company_id:
            try:
                wip_categ = wip_categ.with_company(self.company_id)
            except Exception:
                # ``with_company`` is not present on very old versions; fall back silently
                pass

        # Single category WIP: try common variant field names (adjust if your field differs)
        categ_wip = False
        if wip_categ:
            categ_wip = (
                getattr(wip_categ, 'wip_account_id', False)
                or getattr(wip_categ, 'x_property_account_inventory_categ_id', False)
            )
        categ_wip_id = False
        if categ_wip:
            categ_wip_id = getattr(categ_wip, 'id', False) or categ_wip

        # Location-level accounts as secondary fallback
        src_loc = self.location_id
        dst_loc = self.location_dest_id
        src_out = getattr(src_loc, 'valuation_out_account_id', False) and src_loc.valuation_out_account_id.id or False
        dst_in = getattr(dst_loc, 'valuation_in_account_id', False) and dst_loc.valuation_in_account_id.id or False

        try:
            # 1) Raw Material consumption (stock -> WIP)
            if self.raw_material_production_id:
                debit_wip = categ_wip_id or dst_in
                if debit_wip and categ_val:
                    acc_src = categ_val    # Cr RM category valuation
                    acc_dest = debit_wip   # Dr Category WIP (single account preferred)
                    _logger.info("RM consumption -> Cr RM(%s) / Dr WIP(%s)", acc_src, acc_dest)

            # 2) Finished Goods receipt (WIP -> stock)
            elif self.production_id and self._is_fg_receipt():
                wip = categ_wip_id or src_out
                if wip and categ_val:
                    acc_src = wip       # Credit WIP (source)
                    acc_dest = categ_val # Debit FG Inventory (destination)
                    _logger.info("FG receipt -> Cr WIP(%s) / Dr FG(%s)", acc_src, acc_dest)

            # 3) WIP -> WIP internal transfers
            elif self.production_id:
                credit_wip = categ_wip_id or src_out
                debit_wip = categ_wip_id or dst_in
                if credit_wip and debit_wip:
                    acc_src = credit_wip   # Cr Category WIP
                    acc_dest = debit_wip   # Dr Category WIP
                    _logger.info("WIP→WIP -> Cr WIP(%s) / Dr WIP(%s)", acc_src, acc_dest)

        except Exception as e:
            _logger.exception("WIP account selection failed: %s", e)

        return journal_id, acc_src, acc_dest, acc_valuation


    # def _get_accounting_data_for_valuation(self):
    #     journal_id, acc_src, acc_dest, acc_valuation = super()._get_accounting_data_for_valuation()
    #     self.ensure_one()
    #     if self.production_id:
    #         _logger.info("INSIDE STOCCCKKK MOVEEE")
    #         wip_account = self.product_id.categ_id.x_property_account_inventory_categ_id
    #         finished_account = self.product_id.categ_id.property_stock_valuation_account_id
    #         if wip_account and finished_account:
    #             acc_src = finished_account.id
    #             acc_dest = wip_account.id
    #     return journal_id, acc_src, acc_dest, acc_valuation
