# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.addons.resource.models.resource import make_aware
from datetime import datetime, timedelta, time
from math import ceil
import pytz
import logging

_logger = logging.getLogger(__name__)


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    hours_uom = fields.Many2one('uom.uom', 'Hours', compute="_get_uom_hours")
    partial_confirmation = fields.Boolean('Partial Confirmation allowed', default=True)
    start_without_stock = fields.Boolean('WO Start w/out Components Availability', default=False)
    doc_count = fields.Integer("Number of attached documents", compute='_compute_attached_docs_count')

    @api.constrains('name', 'code')
    def check_unique(self):
        wc_name = self.env['mrp.workcenter'].search([('name', '=', self.name)])
        if len(wc_name) > 1:
            raise UserError(_("Workcenter Name already exists"))
        if self.code:
            wc_code = self.env['mrp.workcenter'].search([('code', '=', self.code)])
            if len(wc_code) > 1:
                raise UserError(_("Workcenter Code already exists"))
        return True

    def _get_uom_hours(self):
        uom = self.env.ref('uom.product_uom_hour', raise_if_not_found=False)
        for record in self:
            if uom:
                record.hours_uom = uom.id
        return True

    def _compute_attached_docs_count(self):
        attachment = self.env['ir.attachment']
        for workcenter in self:
            workcenter.doc_count = attachment.search_count([
                '&',
                ('res_model', '=', 'mrp.workcenter'),
                ('res_id', '=', workcenter.id),
            ])

    def attachment_tree_view(self):
        self.ensure_one()
        domain = ['&', ('res_model', '=', 'mrp.workcenter'), ('res_id', 'in', self.ids)]
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'ir.attachment',
            'view_id': False,
            'view_mode': 'kanban,tree,form',
            'type': 'ir.actions.act_window',
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % (self._name, self.id),
        }

    def _capacity_int(self):
        self.ensure_one()
        return max(int(ceil(self.capacity or 1.0)), 1)

    def _get_dynamic_capacity(self, dt_utc_naive):
        self.ensure_one()
        cal = self.resource_calendar_id
        if not cal:
            return max(int(ceil(self.capacity or 1.0)), 1)

        tz = self._get_calendar_tz()
        dt_local = pytz.utc.localize(dt_utc_naive).astimezone(tz)
        day_of_week = str(dt_local.weekday())
        time_float = dt_local.hour + dt_local.minute / 60.0

        matching = cal.attendance_ids.filtered(
            lambda a: a.dayofweek == day_of_week
            and a.hour_from <= time_float < a.hour_to
            and (a.x_capacity or 0.0) > 0.0
        )
        if matching:
            return max(int(ceil(matching[0].x_capacity)), 1)

        return max(int(ceil(self.capacity or 1.0)), 1)

    # ------------------------------------------------------------------
    # Timezone helpers
    # ------------------------------------------------------------------

    def _get_calendar_tz(self):
        """
        Return the pytz timezone of the workcenter's resource calendar.
        Falls back to UTC if no calendar or no tz defined.

        WHY THIS MATTERS:
            Odoo stores datetimes as UTC naive in the database.
            cal.plan_hours() and _work_intervals() both operate in the
            calendar's local timezone internally.  When plan_hours() receives
            a naive datetime it localizes it using the calendar's tz — so if
            you pass a UTC naive value, plan_hours() treats it as local time,
            causing it to jump 4 hours further ahead than intended (EDT=UTC-4).

            All cursor arithmetic inside _find_next_slot_in_working_hours must
            therefore use calendar-local (Eastern) naive datetimes.  Only at
            the boundaries (input from schedule_workorders, output to wo.write)
            do we convert between UTC naive and local naive.
        """
        self.ensure_one()
        cal = self.resource_calendar_id
        if cal and cal.tz:
            try:
                return pytz.timezone(cal.tz)
            except Exception:
                pass
        return pytz.utc

    def _utc_naive_to_local_naive(self, dt_utc_naive):
        """Convert UTC naive datetime → calendar-local naive datetime."""
        tz = self._get_calendar_tz()
        return pytz.utc.localize(dt_utc_naive).astimezone(tz).replace(tzinfo=None)

    def _local_naive_to_utc_naive(self, dt_local_naive):
        """Convert calendar-local naive datetime → UTC naive datetime."""
        tz = self._get_calendar_tz()
        return tz.localize(dt_local_naive).astimezone(pytz.utc).replace(tzinfo=None)

    # ------------------------------------------------------------------
    # Capacity check — sweep-line peak count
    # ------------------------------------------------------------------

    def _is_slot_free_capacity(self, start_dt, end_dt, exclude_workorder=False):
        """
        Return True if the peak number of concurrently running workorders
        within [start_dt, end_dt) does NOT reach the workcenter's capacity.

        start_dt / end_dt must be UTC naive (as stored in Odoo WO fields).

        WHY sweep-line instead of search_count:
            search_count returns every WO that overlaps the window at all.
            For capacity=2, WO-A on Monday and WO-B on Tuesday (no overlap)
            gives search_count=2 → reports "full" even though no instant has
            2 concurrent jobs.  The sweep-line finds the actual peak.
        """
        self.ensure_one()
        Workorder = self.env["mrp.workorder"]
        cap = self._get_dynamic_capacity(start_dt)
        # cap = self._capacity_int()

        domain = [
            ("workcenter_id", "=", self.id),
            ("state", "not in", ["done", "cancel"]),
            ("date_planned_start_wo", "<", end_dt),
            ("date_planned_finished_wo", ">", start_dt),
        ]
        if exclude_workorder:
            domain.append(("id", "!=", exclude_workorder.id))

        overlapping = Workorder.search(domain)
        if not overlapping:
            return True

        events = []
        for wo in overlapping:
            events.append((fields.Datetime.to_datetime(wo.date_planned_start_wo), +1))
            events.append((fields.Datetime.to_datetime(wo.date_planned_finished_wo), -1))
        events.append((start_dt, +1))
        events.append((end_dt, -1))

        events.sort(key=lambda e: (e[0], e[1]))

        peak = 0
        running = 0
        for _ts, delta in events:
            running += delta
            if running > peak:
                peak = running

        return peak <= cap

    def _working_hours_in_window(self, start_dt, end_dt):
        """
        Returns working hours between start_dt and end_dt.
        start_dt / end_dt are UTC naive.
        """
        self.ensure_one()
        cal = self.resource_calendar_id
        if not cal:
            return (end_dt - start_dt).total_seconds() / 3600.0

        start_aw, _revert = make_aware(start_dt)
        end_aw, _revert2 = make_aware(end_dt)

        intervals = cal._work_intervals(start_aw, end_aw, resource=self.resource_id)
        return sum((e - s).total_seconds() / 3600.0 for s, e, _meta in intervals)

    # ------------------------------------------------------------------
    # Slot finder
    # ------------------------------------------------------------------
    def _find_next_slot_in_working_hours(
        self,
        start_dt,
        duration_minutes,
        deadline_dt=None,
        same_day_only=False,
        exclude_workorder=False,
        max_days=30,
        max_loops=800,
    ):
        self.ensure_one()
        cal = self.resource_calendar_id

        wo = exclude_workorder if exclude_workorder else None

        _logger.info("SLOT SEARCH START")
        _logger.info(
            "WO=%s | WC=%s | start=%s | duration=%s | deadline=%s | same_day=%s",
            wo.name if wo else None,
            self.name,
            start_dt,
            duration_minutes,
            deadline_dt,
            same_day_only,
        )

        duration_minutes = float(duration_minutes or 0.0)
        if duration_minutes <= 0:
            _logger.info("Invalid duration")
            return (False, False)

        # No calendar
        if not cal:
            s = start_dt
            e = s + timedelta(minutes=duration_minutes)

            _logger.info("No calendar | candidate=%s -> %s", s, e)

            if deadline_dt and e > deadline_dt:
                _logger.info("Rejected: deadline")
                return (False, False)

            if same_day_only and e.date() != start_dt.date():
                _logger.info("Rejected: same day")
                return (False, False)

            if self._is_slot_free_capacity(s, e, exclude_workorder=exclude_workorder):
                _logger.info("Slot found | %s -> %s", s, e)
                return (s, e)

            _logger.info("Rejected: capacity")
            return (False, False)

        # Align cursor
        cursor = cal.plan_hours(0.0, start_dt, True)
        _logger.info("Initial cursor=%s", cursor)

        # Horizon
        if same_day_only:
            start_local = self._utc_naive_to_local_naive(start_dt)
            horizon = self._local_naive_to_utc_naive(
                datetime.combine(start_local.date(), time.max)
            )
        else:
            horizon = cursor + timedelta(days=max_days)

        if deadline_dt:
            horizon = min(horizon, deadline_dt)

        _logger.info("Horizon=%s", horizon)

        loops = 0

        while loops < max_loops:
            loops += 1
            _logger.info("Loop=%s | cursor=%s", loops, cursor)

            if cursor > horizon:
                _logger.info("Exit: beyond horizon")
                return (False, False)

            cursor_aw, revert = make_aware(cursor)
            chunk_end = min(horizon, cursor + timedelta(days=7))
            chunk_end_aw, _ = make_aware(chunk_end)

            work_intervals = cal._work_intervals(
                cursor_aw, chunk_end_aw, resource=self.resource_id
            )

            _logger.info("Intervals=%s", len(work_intervals))

            if not work_intervals:
                cursor = cal.plan_hours(0.0, cursor + timedelta(hours=1), True)
                _logger.info("No intervals, move cursor=%s", cursor)
                continue

            advanced = False

            for w_start_aw, w_end_aw, _meta in work_intervals:
                w_start = revert(w_start_aw)
                w_end = revert(w_end_aw)

                _logger.info("Interval=%s -> %s", w_start, w_end)

                cand_start = max(w_start, cursor)
                cand_start = cal.plan_hours(0.0, cand_start, True)

                cand_end = cal.plan_hours(duration_minutes / 60.0, cand_start, True)

                _logger.info("Candidate=%s -> %s", cand_start, cand_end)

                # Overshoot check
                before_aw, _ = make_aware(cand_end - timedelta(seconds=1))
                after_aw, _ = make_aware(cand_end + timedelta(seconds=1))

                end_intervals = list(cal._work_intervals(
                    before_aw, after_aw, resource=self.resource_id
                ))

                if not end_intervals:
                    cursor = cal.plan_hours(0.0, w_end + timedelta(minutes=1), True)
                    _logger.info("Overshoot, move cursor=%s", cursor)
                    advanced = True
                    break

                # Same day
                if same_day_only:
                    cand_end_local = self._utc_naive_to_local_naive(cand_end).date()
                    if cand_end_local != start_local.date():
                        _logger.info("Rejected: same day")
                        return (False, False)

                # Deadline
                if deadline_dt and cand_end > deadline_dt:
                    _logger.info("Rejected: deadline")
                    continue

                # Capacity
                if self._is_slot_free_capacity(
                    cand_start, cand_end,
                    exclude_workorder=exclude_workorder,
                ):
                    _logger.info("Slot found | %s -> %s", cand_start, cand_end)
                    return (cand_start, cand_end)

                _logger.info("Capacity conflict")

                Workorder = self.env["mrp.workorder"]
                domain = [
                    ("workcenter_id", "=", self.id),
                    ("state", "not in", ["done", "cancel"]),
                    ("date_planned_start_wo", "<", cand_end),
                    ("date_planned_finished_wo", ">", cand_start),
                ]
                if exclude_workorder:
                    domain.append(("id", "!=", exclude_workorder.id))

                conflict = Workorder.search(
                    domain, order="date_planned_finished_wo asc", limit=1
                )

                if conflict and conflict.date_planned_finished_wo:
                    _logger.info(
                        "Conflict WO=%s | %s -> %s",
                        conflict.name,
                        conflict.date_planned_start_wo,
                        conflict.date_planned_finished_wo,
                    )
                    cursor = cal.plan_hours(
                        0.0,
                        fields.Datetime.to_datetime(conflict.date_planned_finished_wo),
                        True,
                    )
                    _logger.info("Move cursor=%s", cursor)
                else:
                    cursor = cal.plan_hours(
                        0.0, cand_start + timedelta(minutes=5), True
                    )
                    _logger.info("Move cursor=%s", cursor)

                advanced = True
                break

            if not advanced:
                cursor = cal.plan_hours(0.0, chunk_end, True)
                _logger.info("Move to next chunk, cursor=%s", cursor)

        _logger.info("Exit: max loops reached")
        return (False, False)

    # def _find_next_slot_in_working_hours(
    #     self,
    #     start_dt,
    #     duration_minutes,
    #     deadline_dt=None,
    #     same_day_only=False,
    #     exclude_workorder=False,
    #     max_days=30,
    #     max_loops=800,
    # ):
    #     """
    #     Find the earliest slot >= start_dt that:
    #       - starts within working time (resource calendar)
    #       - consumes duration_minutes in WORKING time (can span multiple
    #         days/shifts via cal.plan_hours)
    #       - respects finite capacity via sweep-line peak count
    #       - ends <= deadline_dt (if provided)
    #       - if same_day_only=True, slot_end must be on same date as start_dt

    #     start_dt and deadline_dt are UTC naive (Odoo standard).
    #     Returned (slot_start, slot_end) are also UTC naive.

    #     TIMEZONE HANDLING:
    #         cal.plan_hours() accepts naive datetimes and treats them as UTC
    #         internally (it converts to calendar-local tz, finds the slot, then
    #         converts back to UTC naive for the return value).

    #         _work_intervals() requires tz-aware inputs (use make_aware).
    #         revert() (returned by make_aware) converts tz-aware → UTC naive.

    #         All cursors and candidate datetimes are kept as UTC naive throughout.
    #         The only conversion needed is at the make_aware / revert boundary
    #         which handles UTC↔aware automatically.

    #         The overshoot probe converts cand_end_utc to UTC-aware before
    #         calling _work_intervals so the calendar correctly evaluates it.
    #     """
    #     self.ensure_one()
    #     cal = self.resource_calendar_id

    #     duration_minutes = float(duration_minutes or 0.0)
    #     if duration_minutes <= 0:
    #         return (False, False)

    #     # No calendar → continuous time
    #     if not cal:
    #         s = start_dt
    #         e = s + timedelta(minutes=duration_minutes)
    #         if deadline_dt and e > deadline_dt:
    #             return (False, False)
    #         if same_day_only and e.date() != start_dt.date():
    #             return (False, False)
    #         if self._is_slot_free_capacity(s, e, exclude_workorder=exclude_workorder):
    #             return (s, e)
    #         return (False, False)

    #     # Normalize cursor to next working instant.
    #     # plan_hours accepts UTC naive and returns UTC naive.
    #     cursor = cal.plan_hours(0.0, start_dt, True)

    #     # Build horizon (UTC naive)
    #     if same_day_only:
    #         # Convert start_dt to local to get the local date, then back to UTC
    #         start_local = self._utc_naive_to_local_naive(start_dt)
    #         horizon = self._local_naive_to_utc_naive(
    #             datetime.combine(start_local.date(), time.max)
    #         )
    #     else:
    #         horizon = cursor + timedelta(days=max_days)
    #     if deadline_dt:
    #         horizon = min(horizon, deadline_dt)

    #     loops = 0
    #     while loops < max_loops:
    #         loops += 1

    #         if cursor > horizon:
    #             return (False, False)

    #         # Fetch working intervals in next 7-day chunk (UTC aware)
    #         cursor_aw, revert = make_aware(cursor)
    #         chunk_end = min(horizon, cursor + timedelta(days=7))
    #         chunk_end_aw, _ = make_aware(chunk_end)

    #         work_intervals = cal._work_intervals(
    #             cursor_aw, chunk_end_aw, resource=self.resource_id
    #         )
    #         if not work_intervals:
    #             cursor = cal.plan_hours(0.0, cursor + timedelta(hours=1), True)
    #             continue

    #         advanced = False

    #         for w_start_aw, w_end_aw, _meta in work_intervals:
    #             # revert gives UTC naive
    #             w_start = revert(w_start_aw)
    #             w_end = revert(w_end_aw)

    #             # Candidate start: later of interval start or current cursor
    #             # Both UTC naive — safe to compare directly
    #             cand_start = max(w_start, cursor)

    #             # Snap to next working instant (UTC naive)
    #             cand_start = cal.plan_hours(0.0, cand_start, True)

    #             # Consume duration in WORKING time (UTC naive)
    #             cand_end = cal.plan_hours(duration_minutes / 60.0, cand_start, True)

    #             # Validate cand_end is within working hours.
    #             # plan_hours can overshoot past a shift end due to floating-point
    #             # precision (e.g. 722.16 min from mid-shift lands past shift end).
    #             # Probe [cand_end-1s, cand_end+1s] — if no working intervals,
    #             # plan_hours overshot; jump cursor past current interval and retry.
    #             cand_end_before_aw, _ = make_aware(cand_end - timedelta(seconds=1))
    #             cand_end_after_aw, _ = make_aware(cand_end + timedelta(seconds=1))
    #             end_intervals = list(cal._work_intervals(
    #                 cand_end_before_aw, cand_end_after_aw,
    #                 resource=self.resource_id,
    #             ))
    #             if not end_intervals:
    #                 # Overshot — jump to next shift start
    #                 cursor = cal.plan_hours(0.0, w_end + timedelta(minutes=1), True)
    #                 advanced = True
    #                 break

    #             # same-day-only guard (convert to local for date comparison)
    #             if same_day_only:
    #                 cand_end_local_date = self._utc_naive_to_local_naive(cand_end).date()
    #                 if cand_end_local_date != start_local.date():
    #                     return (False, False)

    #             # deadline guard (UTC naive)
    #             if deadline_dt and cand_end > deadline_dt:
    #                 continue

    #             # Capacity check (UTC naive — matches stored WO fields)
    #             if self._is_slot_free_capacity(
    #                 cand_start, cand_end,
    #                 exclude_workorder=exclude_workorder,
    #             ):
    #                 return (cand_start, cand_end)

    #             # Capacity conflict: jump cursor to earliest conflicting WO end
    #             Workorder = self.env["mrp.workorder"]
    #             domain = [
    #                 ("workcenter_id", "=", self.id),
    #                 ("state", "not in", ["done", "cancel"]),
    #                 ("date_planned_start_wo", "<", cand_end),
    #                 ("date_planned_finished_wo", ">", cand_start),
    #             ]
    #             if exclude_workorder:
    #                 domain.append(("id", "!=", exclude_workorder.id))

    #             conflict = Workorder.search(
    #                 domain, order="date_planned_finished_wo asc", limit=1
    #             )
    #             if conflict and conflict.date_planned_finished_wo:
    #                 cursor = cal.plan_hours(
    #                     0.0,
    #                     fields.Datetime.to_datetime(conflict.date_planned_finished_wo),
    #                     True,
    #                 )
    #             else:
    #                 cursor = cal.plan_hours(
    #                     0.0, cand_start + timedelta(minutes=5), True
    #                 )

    #             advanced = True
    #             break

    #         if not advanced:
    #             # No candidate in this chunk; move to next chunk
    #             cursor = cal.plan_hours(0.0, chunk_end, True)

    #     return (False, False)