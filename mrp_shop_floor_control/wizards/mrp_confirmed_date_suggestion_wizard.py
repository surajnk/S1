# -*- coding: utf-8 -*-
import datetime
from datetime import timedelta, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpConfirmedDateSuggestionWizard(models.TransientModel):
    _name = "mrp.confirmed.date.suggestion.wizard"
    _description = "Confirmed Date Suggestions"

    production_id = fields.Many2one("mrp.production", required=True, readonly=True)

    calculation_mode = fields.Selection([
        ("first", "Based on First Workorder"),
        ("bottleneck", "Based on Bottleneck Workorder"),
        ("chain", "Based on Entire Chain (All Workorders)"),
    ], string="Suggestion Mode", default="chain", required=True)

    cutoff_time = fields.Float(
        string="Cutoff Time (Hours)",
        default=5.0,
        help="Confirmed deadline time on Confirmed Date. Example: 5.0 means 05:00."
    )
    suggestion_count = fields.Integer(string="How many options", default=5)

    line_ids = fields.One2many(
        "mrp.confirmed.date.suggestion.wizard.line",
        "wizard_id",
        string="Suggestions",
        readonly=True,
    )

    # ---------- helpers ----------
    def _cutoff_as_time(self):
        hours = int(self.cutoff_time or 0.0)
        minutes = int(round(((self.cutoff_time or 0.0) - hours) * 60))
        return time(hours, minutes, 0)

    def _confirmed_date_from_finish(self, finish_dt, cutoff):
        # Rule: finish <= confirmed_date at cutoff
        if finish_dt.time() <= cutoff:
            return finish_dt.date()
        return (finish_dt + timedelta(days=1)).date()

    def _get_interval_minutes_for_production(self, production):
        """Same logic as schedule_workorders() for interval gaps."""
        floating = self.env["mrp.floating.times"].search(
            [("warehouse_id", "=", production.picking_type_id.warehouse_id.id)],
            limit=1
        )
        if not floating:
            raise UserError(_(
                "Floating Times record has not been created yet for the warehouse: %s"
            ) % production.picking_type_id.warehouse_id.name)

        yards = production.x_order_master_yards or 0
        if 0 < yards <= 10000:
            return floating.mrp_operations_first * 60
        elif yards <= 25000:
            return floating.mrp_operations_second * 60
        elif yards <= 50000:
            return floating.mrp_operations_third * 60
        elif yards <= 100000:
            return floating.mrp_operations_fourth * 60
        else:
            return floating.mrp_operations_fifth * 60

    def _collect_slot_suggestions_for_workorder(self, wo, start_dt, limit):
        """Return unique suggested confirmed dates from next available slots of ONE workorder."""
        wc = wo.workcenter_id
        if not wc:
            return []

        cutoff = self._cutoff_as_time()
        suggestions = []
        cursor = start_dt

        for _ in range(limit * 10):
            slot_start, slot_end = wc._find_next_slot_in_working_hours(
                start_dt=cursor,
                duration_minutes=wo.duration_expected,
                deadline_dt=None,
                same_day_only=False,
                exclude_workorder=wo,
                max_days=180,
            )
            if not slot_start:
                break

            sug_date = self._confirmed_date_from_finish(slot_end, cutoff)
            suggestions.append((slot_start, slot_end, sug_date))

            if len(suggestions) >= limit * 3:
                break

            cursor = slot_start + timedelta(minutes=1)

        # Deduplicate by suggested date
        seen = set()
        unique = []
        for s, e, d in suggestions:
            if d in seen:
                continue
            seen.add(d)
            unique.append((s, e, d))
            if len(unique) >= limit:
                break
        return unique

    def _get_bottleneck_workorder(self, workorders, start_dt):
        """
        Bottleneck WO = the WO whose earliest possible finish (from start_dt) is latest.
        This is independent-slot estimation (not chain simulation).
        """
        worst_wo = None
        worst_end = None

        for wo in workorders:
            wc = wo.workcenter_id
            if not wc:
                continue

            s, e = wc._find_next_slot_in_working_hours(
                start_dt=start_dt,
                duration_minutes=wo.duration_expected,
                deadline_dt=None,
                same_day_only=False,
                exclude_workorder=wo,
                max_days=180,
            )
            if not s:
                # If a WO has no slot at all, treat as worst immediately
                return wo

            if not worst_end or e > worst_end:
                worst_end = e
                worst_wo = wo

        return worst_wo

    def _simulate_chain_finish(self, workorders, start_dt, interval_minutes):
        """
        Dry-run simulation of the entire WO chain WITHOUT writing:
        schedules sequentially from start_dt using wc._find_next_slot_in_working_hours.
        Returns (first_slot_start, last_finish) or (False, False) if cannot find.
        """
        cursor = start_dt
        first_start = None
        last_end = None

        for wo in workorders:
            wc = wo.workcenter_id
            if not wc:
                return (False, False)

            s, e = wc._find_next_slot_in_working_hours(
                start_dt=cursor,
                duration_minutes=wo.duration_expected,
                deadline_dt=None,
                same_day_only=False,
                exclude_workorder=wo,
                max_days=365,
            )
            if not s:
                return (False, False)

            if first_start is None:
                first_start = s
            last_end = e
            cursor = e + timedelta(minutes=interval_minutes)

        return (first_start, last_end)

    def _collect_chain_suggestions(self, workorders, start_dt, interval_minutes, limit):
        """
        Find multiple possible confirmed dates for the ENTIRE chain by running multiple dry-run simulations.
        Each next option shifts the chain-start search slightly forward.
        """
        cutoff = self._cutoff_as_time()
        results = []
        cursor = start_dt

        for _ in range(limit * 15):
            first_start, chain_finish = self._simulate_chain_finish(workorders, cursor, interval_minutes)
            if not first_start:
                break

            sug_date = self._confirmed_date_from_finish(chain_finish, cutoff)
            results.append((first_start, chain_finish, sug_date))

            if len(results) >= limit * 3:
                break

            # move forward to get a different alternative
            cursor = first_start + timedelta(minutes=1)

        # Deduplicate by suggested date
        seen = set()
        unique = []
        for s, e, d in results:
            if d in seen:
                continue
            seen.add(d)
            unique.append((s, e, d))
            if len(unique) >= limit:
                break
        return unique

    # ---------- main ----------
    def action_compute(self):
        self.ensure_one()
        production = self.production_id
        if not production:
            raise UserError(_("Manufacturing Order not found."))

        workorders = production.workorder_ids.sorted(key=lambda wo: (wo.sequence, wo.id))
        if not workorders:
            raise UserError(_("No workorders found on this Manufacturing Order."))

        start_dt = fields.Datetime.now()
        cutoff = self._cutoff_as_time()
        limit = self.suggestion_count or 5

        # Clear old lines
        self.line_ids.unlink()

        interval_minutes = self._get_interval_minutes_for_production(production)

        # Decide which strategy
        suggestions = []
        title_note = ""

        if self.calculation_mode == "first":
            wo = workorders[0]
            title_note = _("Based on first workorder: %s") % (wo.display_name,)
            suggestions = self._collect_slot_suggestions_for_workorder(wo, start_dt, limit)

            # For lines: slot_start/slot_end are actual WO1 slot
            line_wo = wo
            line_wc = wo.workcenter_id

            line_vals = []
            for slot_start, slot_end, sug_date in suggestions:
                sug_deadline = datetime.datetime.combine(sug_date, cutoff)
                line_vals.append((0, 0, {
                    "mode_note": title_note,
                    "workorder_id": line_wo.id,
                    "workcenter_id": line_wc.id,
                    "slot_start": slot_start,
                    "slot_end": slot_end,
                    "suggested_confirmed_date": sug_date,
                    "suggested_deadline": sug_deadline,
                    "chain_finish": False,
                }))
            self.write({"line_ids": line_vals})

        elif self.calculation_mode == "bottleneck":
            wo = self._get_bottleneck_workorder(workorders, start_dt)
            if not wo:
                raise UserError(_("Unable to detect bottleneck workorder (missing workcenters)."))

            title_note = _("Based on bottleneck workorder: %s") % (wo.display_name,)
            suggestions = self._collect_slot_suggestions_for_workorder(wo, start_dt, limit)

            line_vals = []
            for slot_start, slot_end, sug_date in suggestions:
                sug_deadline = datetime.datetime.combine(sug_date, cutoff)
                line_vals.append((0, 0, {
                    "mode_note": title_note,
                    "workorder_id": wo.id,
                    "workcenter_id": wo.workcenter_id.id,
                    "slot_start": slot_start,
                    "slot_end": slot_end,
                    "suggested_confirmed_date": sug_date,
                    "suggested_deadline": sug_deadline,
                    "chain_finish": False,
                }))
            self.write({"line_ids": line_vals})

        else:
            # chain
            title_note = _("Based on entire chain (all workorders).")
            suggestions = self._collect_chain_suggestions(workorders, start_dt, interval_minutes, limit)

            line_vals = []
            # For chain, we show: first_start as slot_start, chain_finish in chain_finish
            for first_start, chain_finish, sug_date in suggestions:
                sug_deadline = datetime.datetime.combine(sug_date, cutoff)
                line_vals.append((0, 0, {
                    "mode_note": title_note,
                    "workorder_id": workorders[0].id,
                    "workcenter_id": workorders[0].workcenter_id.id,
                    "slot_start": first_start,
                    "slot_end": False,
                    "suggested_confirmed_date": sug_date,
                    "suggested_deadline": sug_deadline,
                    "chain_finish": chain_finish,
                }))
            self.write({"line_ids": line_vals})

        if not self.line_ids:
            raise UserError(_("No suggestions found within the search horizon."))

        return {
            "type": "ir.actions.act_window",
            "name": _("Suggested Confirmed Dates"),
            "res_model": "mrp.confirmed.date.suggestion.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }


class MrpConfirmedDateSuggestionWizardLine(models.TransientModel):
    _name = "mrp.confirmed.date.suggestion.wizard.line"
    _description = "Confirmed Date Suggestion Line"

    wizard_id = fields.Many2one("mrp.confirmed.date.suggestion.wizard", required=True, ondelete="cascade")

    mode_note = fields.Char(readonly=True)
    workorder_id = fields.Many2one("mrp.workorder", readonly=True)
    workcenter_id = fields.Many2one("mrp.workcenter", readonly=True)

    slot_start = fields.Datetime(readonly=True)
    slot_end = fields.Datetime(readonly=True)

    # For chain mode: final chain completion datetime
    chain_finish = fields.Datetime(readonly=True)

    suggested_confirmed_date = fields.Date(readonly=True)
    suggested_deadline = fields.Datetime(readonly=True)
