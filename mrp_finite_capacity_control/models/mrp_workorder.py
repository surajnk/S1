# -*- coding: utf-8 -*-
from math import ceil
from datetime import datetime, timedelta, time
from odoo import _, fields, models, api
from odoo.exceptions import ValidationError
from odoo.addons.resource.models.resource import make_aware
import logging

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    x_customer_name = fields.Many2one(
        'res.partner',
        string='Customer',
        compute='_compute_customer_name',
        store=True,
    )

    @api.depends('production_id.x_customer_name')
    def _compute_customer_name(self):
        stock_order_partner = self.env['res.partner'].search(
            [('name', '=', 'STOCK ORDER')], limit=1
        )
        for workorder in self:
            if workorder.production_id.x_customer_name:
                workorder.x_customer_name = workorder.production_id.x_customer_name
            else:
                workorder.x_customer_name = stock_order_partner

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_finite_capacity_enabled(self):
        param_value = self.env['ir.config_parameter'].sudo().get_param(
            'mrp_finite_capacity_control.finite_capacity_scheduling'
        )
        return param_value in ['True', True, '1', 1]

    def _get_workcenter_working_intervals(self, workcenter, dt_start, dt_end):
        """
        Return (intervals, total_hours) for *workcenter* between dt_start and
        dt_end (naive UTC datetimes, as stored by Odoo).

        intervals   : list of (naive_start, naive_end) pairs
        total_hours : float — sum of working seconds converted to hours

        If the workcenter has no resource calendar the entire window is
        treated as working time.
        """
        cal = workcenter.resource_calendar_id
        if not cal:
            total = (dt_end - dt_start).total_seconds() / 3600.0
            _logger.info(
                "[FiniteCap] _get_workcenter_working_intervals | WC '%s' has no calendar"
                " → treating full window as working time (%.2f h)",
                workcenter.display_name, total,
            )
            return [(dt_start, dt_end)], total

        start_aw, _ = make_aware(dt_start)
        end_aw, _ = make_aware(dt_end)

        raw_intervals = cal._work_intervals(
            start_aw, end_aw, resource=workcenter.resource_id
        )
        result = []
        total = 0.0
        for ivl_start, ivl_end, _meta in raw_intervals:
            s = ivl_start.replace(tzinfo=None)
            e = ivl_end.replace(tzinfo=None)
            result.append((s, e))
            total += (e - s).total_seconds() / 3600.0

        _logger.info(
            "[FiniteCap] _get_workcenter_working_intervals | WC '%s' | Calendar '%s'"
            " | Window %s → %s | Intervals found: %d | Total working hours: %.2f h",
            workcenter.display_name,
            cal.name,
            dt_start,
            dt_end,
            len(result),
            total,
        )
        for i, (s, e) in enumerate(result, 1):
            _logger.info(
                "[FiniteCap]   Interval %d: %s → %s (%.2f h)",
                i, s, e, (e - s).total_seconds() / 3600.0,
            )

        return result, total

    def _datetime_is_within_working_hours(self, workcenter, dt):
        """
        Return True if *dt* (naive UTC) falls inside a working interval of
        *workcenter*.  A datetime coinciding exactly with a shift boundary
        (start or end) is considered valid.

        WHY probe both sides:
            Probing only [dt, dt+1s] fails when dt is exactly at shift end
            (e.g. 17:00:00) because the interval [17:00:00, 17:00:01] has
            zero working time — the shift ended at 17:00:00.  This causes
            slot-finder-generated end times that land exactly on shift end
            to be wrongly rejected by Guard 2.

            Probing [dt-1s, dt+1s] catches both cases:
              - dt is a shift start  → [dt-1s, dt] has no working time,
                                       [dt, dt+1s] has working time → pass
              - dt is a shift end    → [dt-1s, dt] has working time → pass
              - dt is mid-shift      → both sides have working time → pass
              - dt is truly outside  → neither side has working time → fail
        """
        cal = workcenter.resource_calendar_id
        if not cal:
            _logger.info(
                "[FiniteCap] _datetime_is_within_working_hours | WC '%s' has no calendar"
                " → %s is always valid",
                workcenter.display_name, dt,
            )
            return True

        # Probe [dt-1s, dt+1s] to handle exact shift boundaries
        dt_before_aw, _ = make_aware(dt - timedelta(seconds=1))
        dt_after_aw, _ = make_aware(dt + timedelta(seconds=1))

        intervals = list(cal._work_intervals(
            dt_before_aw, dt_after_aw, resource=workcenter.resource_id
        ))
        result = len(intervals) > 0

        _logger.info(
            "[FiniteCap] _datetime_is_within_working_hours | WC '%s' | Calendar '%s'"
            " | Checking dt: %s | Probe window: %s → %s"
            " | Intervals matched: %d | Within working hours: %s",
            workcenter.display_name,
            cal.name,
            dt,
            dt_before_aw,
            dt_after_aw,
            len(intervals),
            result,
        )
        return result

    def _get_workcenter_day_hours(self, workcenter, day_date):
        """Convenience: total working hours for *workcenter* on *day_date*."""
        day_start = datetime.combine(day_date, time.min)
        day_end = datetime.combine(day_date, time.max)
        _intervals, total = self._get_workcenter_working_intervals(
            workcenter, day_start, day_end
        )
        _logger.info(
            "[FiniteCap] _get_workcenter_day_hours | WC '%s' | Day %s | Hours: %.2f",
            workcenter.display_name, day_date, total,
        )
        return total

    # ------------------------------------------------------------------
    # Constraint
    # ------------------------------------------------------------------

    @api.constrains('date_planned_start_wo', 'date_planned_finished_wo', 'workcenter_id')
    def _check_finite_capacity_schedule(self):
        if not self._is_finite_capacity_enabled():
            _logger.info("[FiniteCap] Finite capacity scheduling is DISABLED — skipping check.")
            return

        Workorder = self.env['mrp.workorder']

        for workorder in self:
            _logger.info(
                "[FiniteCap] ── BEGIN CHECK ── WO '%s' (id=%s) | MO '%s'"
                " | WC '%s' | Start: %s | End: %s",
                workorder.name or '(no name)',
                workorder.id,
                workorder.production_id.name or '(no MO)',
                workorder.workcenter_id.display_name if workorder.workcenter_id else '(none)',
                workorder.date_planned_start_wo,
                workorder.date_planned_finished_wo,
            )

            if (
                not workorder.date_planned_start_wo
                or not workorder.date_planned_finished_wo
                or not workorder.workcenter_id
            ):
                _logger.info(
                    "[FiniteCap] WO '%s' — missing start, end, or workcenter → skipping.",
                    workorder.name or workorder.id,
                )
                continue

            wc = workorder.workcenter_id
            wo_start = fields.Datetime.to_datetime(workorder.date_planned_start_wo)
            wo_end = fields.Datetime.to_datetime(workorder.date_planned_finished_wo)

            _logger.info(
                "[FiniteCap] Workcenter details | Name: '%s' | Capacity: %s"
                " | Machines (ceil): %s | Time Efficiency: %s%%"
                " | Calendar: '%s'",
                wc.display_name,
                wc.capacity,
                ceil(wc.capacity or 1.0),
                wc.time_efficiency,
                wc.resource_calendar_id.name if wc.resource_calendar_id else 'None',
            )

            # ----------------------------------------------------------
            # Guard 1 – past date
            # ----------------------------------------------------------
            _logger.info("[FiniteCap] Guard 1 — past date check")
            mo_confirmed_date = workorder.production_id.x_mrp_confirmed_date
            _logger.info(
                "[FiniteCap]   MO confirmed date: %s | Today: %s",
                mo_confirmed_date, fields.Date.today(),
            )

            if (
                mo_confirmed_date
                and fields.Date.to_date(mo_confirmed_date) < fields.Date.today()
            ):
                _logger.warning(
                    "[FiniteCap] Guard 1 FAIL | WO '%s' | MO confirmed date %s is in the past.",
                    workorder.name or workorder.id, mo_confirmed_date,
                )
                raise ValidationError(
                    _(
                        "You cannot schedule workorder %(wo)s in the past."
                        " Current date is %(today)s."
                    ) % {
                        'wo': workorder.name or workorder.id,
                        'today': fields.Date.to_string(fields.Date.today()),
                    }
                )
            _logger.info("[FiniteCap] Guard 1 PASS")

            # ----------------------------------------------------------
            # Guard 2 – working hours boundary check
            # ----------------------------------------------------------
            _logger.info("[FiniteCap] Guard 2 — working hours boundary check")

            if wc.resource_calendar_id:
                _logger.info(
                    "[FiniteCap]   Checking START boundary: %s", wo_start,
                )
                start_ok = self._datetime_is_within_working_hours(wc, wo_start)
                if not start_ok:
                    _logger.warning(
                        "[FiniteCap] Guard 2 FAIL (start) | WO '%s' | WC '%s'"
                        " | Start %s is outside calendar '%s'.",
                        workorder.name or workorder.id,
                        wc.display_name,
                        wo_start,
                        wc.resource_calendar_id.name,
                    )
                    raise ValidationError(
                        _(
                            "The start time %(start)s for workorder %(wo)s"
                            " falls outside the working hours of"
                            " workcenter %(wc)s."
                            " Please choose a time within the workcenter's"
                            " calendar."
                        ) % {
                            'wo': workorder.name or workorder.id,
                            'wc': wc.display_name,
                            'start': fields.Datetime.to_string(wo_start),
                        }
                    )

                _logger.info(
                    "[FiniteCap]   Checking END boundary: %s", wo_end,
                )
                end_ok = self._datetime_is_within_working_hours(wc, wo_end)
                if not end_ok:
                    _logger.warning(
                        "[FiniteCap] Guard 2 FAIL (end) | WO '%s' | WC '%s'"
                        " | End %s is outside calendar '%s'.",
                        workorder.name or workorder.id,
                        wc.display_name,
                        wo_end,
                        wc.resource_calendar_id.name,
                    )
                    raise ValidationError(
                        _(
                            "The end time %(end)s for workorder %(wo)s"
                            " falls outside the working hours of"
                            " workcenter %(wc)s."
                            " Please choose a time within the workcenter's"
                            " calendar."
                        ) % {
                            'wo': workorder.name or workorder.id,
                            'wc': wc.display_name,
                            'end': fields.Datetime.to_string(wo_end),
                        }
                    )
                _logger.info("[FiniteCap] Guard 2 PASS | Start and end both within working hours.")
            else:
                _logger.info(
                    "[FiniteCap] Guard 2 SKIP | WC '%s' has no resource calendar.",
                    wc.display_name,
                )

            # ----------------------------------------------------------
            # Guard 3 – concurrent machine count (sweep-line)
            # ----------------------------------------------------------
            _logger.info("[FiniteCap] Guard 3 — concurrent machine count (sweep-line)")

            machine_count = ceil(wc.capacity or 1.0)

            overlapping = Workorder.search([
                ('id', '!=', workorder.id),
                ('workcenter_id', '=', wc.id),
                ('date_planned_start_wo', '<', workorder.date_planned_finished_wo),
                ('date_planned_finished_wo', '>', workorder.date_planned_start_wo),
                ('state', 'not in', ['done', 'cancel']),
            ])

            _logger.info(
                "[FiniteCap]   Machine count (ceil of capacity %.2f): %d"
                " | Overlapping WOs found: %d",
                wc.capacity or 1.0, machine_count, len(overlapping),
            )
            for ow in overlapping:
                _logger.info(
                    "[FiniteCap]   Overlapping WO: '%s' (id=%s) | %s → %s | State: %s",
                    ow.name or '(no name)',
                    ow.id,
                    ow.date_planned_start_wo,
                    ow.date_planned_finished_wo,
                    ow.state,
                )

            events = []
            for wo in overlapping:
                events.append((
                    fields.Datetime.to_datetime(wo.date_planned_start_wo), +1
                ))
                events.append((
                    fields.Datetime.to_datetime(wo.date_planned_finished_wo), -1
                ))
            events.append((wo_start, +1))
            events.append((wo_end, -1))

            # ends (-1) sort before starts (+1) at the same timestamp
            events.sort(key=lambda e: (e[0], e[1]))

            _logger.info("[FiniteCap]   Sweep-line events (sorted):")
            peak = 0
            running = 0
            for ts, delta in events:
                running += delta
                if running > peak:
                    peak = running
                _logger.info(
                    "[FiniteCap]     %s  delta=%+d  running=%d  peak=%d",
                    ts, delta, running, peak,
                )

            _logger.info(
                "[FiniteCap]   Sweep result | Peak concurrent: %d | Machine count: %d | %s",
                peak,
                machine_count,
                "OVER CAPACITY" if peak > machine_count else "within capacity",
            )

            if peak > machine_count:
                _logger.warning(
                    "[FiniteCap] Guard 3 FAIL | WO '%s' | WC '%s'"
                    " | Peak=%d exceeds machine_count=%d"
                    " | Window: %s → %s",
                    workorder.name or workorder.id,
                    wc.display_name,
                    peak,
                    machine_count,
                    wo_start,
                    wo_end,
                )
                raise ValidationError(
                    _(
                        "Workcenter %(wc)s is already at full capacity"
                        " (%(cap)s simultaneous machine(s))."
                        " Peak concurrent workorders would be %(peak)s."
                        " Scheduled window: %(start)s \u2013 %(end)s."
                    ) % {
                        'wc': wc.display_name,
                        'cap': machine_count,
                        'peak': peak,
                        'start': fields.Datetime.to_string(wo_start),
                        'end': fields.Datetime.to_string(wo_end),
                    }
                )

            _logger.info("[FiniteCap] Guard 3 PASS")
            _logger.info(
                "[FiniteCap] ── END CHECK ── WO '%s' (id=%s) — all guards passed.",
                workorder.name or '(no name)', workorder.id,
            )