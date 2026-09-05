from datetime import datetime, time

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpWorkorderScheduleWizard(models.TransientModel):
    _name = 'mrp.workorder.schedule.wizard'
    _description = 'MRP Workorder Schedule Wizard'

    date_from = fields.Date(
        string='Date From',
        required=True,
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        string='Date To',
        required=True,
        default=fields.Date.context_today,
    )

    # ---------------- Helpers ----------------

    def _get_datetime_range(self):
        """Return [start_dt, end_dt] for date range in server datetime format."""
        self.ensure_one()
        if self.date_from > self.date_to:
            raise UserError(_('The start date must be earlier than or equal to the end date.'))
        start_dt = datetime.combine(self.date_from, time.min)
        end_dt = datetime.combine(self.date_to, time.max)
        return (
            fields.Datetime.to_string(start_dt),
            fields.Datetime.to_string(end_dt),
        )

    def _mo_customer_name(self, production):
        """Best-effort guess of the customer for a given MO."""
        SaleOrder = self.env['sale.order']

        # 1) Direct sale_id on the MO (standard when MO comes from SO)
        sale = getattr(production, 'sale_id', False)
        if sale and sale.partner_id:
            return sale.partner_id.display_name or ''

        # 2) Via procurement group
        group = getattr(production, 'procurement_group_id', False)
        if group:
            so = SaleOrder.search([('procurement_group_id', '=', group.id)], limit=1)
            if so and so.partner_id:
                return so.partner_id.display_name or ''

        # 3) Via stock moves (finished + raw)
        for mv in (production.move_finished_ids | production.move_raw_ids):
            sol = getattr(mv, 'sale_line_id', False)
            if sol and sol.order_id and sol.order_id.partner_id:
                return sol.order_id.partner_id.display_name or ''

        # 4) Via origin field (often contains the SO name)
        if production.origin:
            so = SaleOrder.search([('name', '=', production.origin)], limit=1)
            if so and so.partner_id:
                return so.partner_id.display_name or ''

        # Fallback
        return ''

    def _categorize_workcenter(self, workcenter):
        """Classify a workcenter into report columns."""
        name = (workcenter.display_name or '').lower()
        code = (getattr(workcenter, 'code', '') or '').lower()
        text = f"{name} {code}"

        # Sheeter?
        is_sheeter = any(k in text for k in ('sheeter', 'sht'))

        # Prefer boolean for embosser if present
        is_emb = bool(getattr(workcenter, 'embosser', False))
        if not is_emb:
            is_emb = any(k in text for k in ('embw', 'emboss', 'emb'))

        cats = {
            'sht': is_sheeter,
            'ctr': any(k in text for k in ('ctr', 'cut')) and not (is_sheeter or is_emb),
            'plt': any(k in text for k in ('plat', 'plate', 'plating')),
            'lam': any(k in text for k in ('lam', 'lamination', 'lami')),
            'prt': any(k in text for k in ('prt', 'ptr')),
            'embossing': is_emb,
            'roll': any(k in text for k in ('roll', 'rew', 'rwd')) and not (is_sheeter or is_emb),
        }
        if not any(cats.values()):
            cats['ctr'] = True
        return cats

    def _sheeter_bucket(self, workcenter):
        """Return sheeter group key or None: 'sheeter_12', 'sheeter_3', 'sheeter_4'."""
        name = (workcenter.display_name or '').lower()
        code = (getattr(workcenter, 'code', '') or '').lower()
        text = f"{name} {code}"

        # Adjust tokens to match your real codes/names
        if any(k in text for k in ('sh01', 'sh02', 'sheeter 1', 'sheeter1', 'sheeter 2', 'sheeter2')):
            return 'sheeter_12'
        if any(k in text for k in ('sh03', 'sheeter 3', 'sheeter3')):
            return 'sheeter_3'
        if any(k in text for k in ('sh04', 'sheeter 4', 'sheeter4')):
            return 'sheeter_4'
        return None

    def _short_wc_label(self, workcenter):
        code = (getattr(workcenter, 'code', '') or '').strip()
        if code:
            return code
        name = (workcenter.display_name or '').strip()
        return name.split()[0] if name else ''

    def _fmt(self, val, digits=2, use_grouping=False):
        """Return a safe string like 1,234.50 or 1234.50 (no formatLang)."""
        if val is None:
            return ''
        if use_grouping:
            return f"{val:,.{digits}f}"
        return f"{val:.{digits}f}"

    # ---------------- Data prep ----------------

    def _prepare_report_data(self):
        """
        Build:
          - daily pages (days)
          - daily footers
          - weekly_summary (for the separate weekly pages)
        """
        self.ensure_one()
        start_dt, end_dt = self._get_datetime_range()

        companies = getattr(self.env, 'companies', self.env.company)
        domain = [
            ('x_confirmed_date', '!=', False),
            ('x_confirmed_date', '>=', self.date_from),
            ('x_confirmed_date', '<=', self.date_to),
            ('company_id', 'in', companies.ids),
        ]
        # domain = [
        #     ('date_planned_start', '!=', False),
        #     ('date_planned_start', '>=', start_dt),
        #     ('date_planned_start', '<=', end_dt),
        #     ('company_id', 'in', companies.ids),
        # ]
        Workorder = self.env['mrp.workorder']
        workorders = Workorder.search(domain, order='production_id, sequence, id')

        # Group WOs by MO
        by_mo = {}
        for wo in workorders:
            by_mo.setdefault(wo.production_id, []).append(wo)

        days_map = {}          # { date -> [row, ...] }
        grand_total_qty = 0.0
        grand_total_remaining = 0.0

        for production, wo_list in by_mo.items():
            # sort WOs inside the MO by sequence (then id)
            wo_list_sorted = sorted(
                wo_list,
                key=lambda w: (w.sequence or 0, w.id),
            )
            first_wo = wo_list_sorted[0]

            # Day (from first WO) in user tz
            planned = first_wo.x_confirmed_date or production.x_mrp_confirmed_date
            if not planned:
                continue
            day = planned 
            # planned = first_wo.date_planned_start or production.date_planned_start
            # if not planned:
            #     continue
            # local_dt = fields.Datetime.context_timestamp(self, planned)
            # day = local_dt.date()

            # Quantities from FIRST WO
            qty_planned = float(getattr(first_wo, 'qty_output_wo', 0.0) or 0.0)
            qty_done = float(getattr(first_wo, 'total_produce_quantity', 0.0) or 0.0)
            qty_remaining = max(0.0, qty_planned - qty_done)

            # Per-category chips from ALL WOs of this MO
            buckets = {
                'ctr': [], 'plt': [], 'lam': [], 'prt': [],
                'embossing': [], 'roll': [], 'sht': [],
            }
            seen_label = set()

            def _add_chip(cat, label, is_done):
                if label and (cat, label) not in seen_label:
                    buckets[cat].append({'label': label, 'is_done': is_done})
                    seen_label.add((cat, label))

            all_wos = sorted(
                production.workorder_ids,
                key=lambda w: (w.sequence or 0, w.id),
            )
            for wo in all_wos:
                cats = self._categorize_workcenter(wo.workcenter_id)
                short = self._short_wc_label(wo.workcenter_id)
                for cat, active in cats.items():
                    if active and cat in buckets:
                        label = (
                            wo.operation_id.name
                            if (cat == 'embossing'
                                and getattr(wo, 'operation_id', False)
                                and wo.operation_id.name)
                            else short
                        )
                        _add_chip(cat, label, wo.state == 'done')

            # Build row (one per MO)
            row = {
                'order_no': production.name,
                'part_no': production.product_id.default_code or '',
                'customer': self._mo_customer_name(production),
                'wo_yards': qty_planned,
                'wo_yards_s': self._fmt(qty_planned, digits=2),
                'remain_yd': qty_remaining,
                'remain_yd_s': self._fmt(qty_remaining, digits=2),

                'ctr': buckets['ctr'],
                'plt': buckets['plt'],
                'lam': buckets['lam'],
                'prt': buckets['prt'],
                'embossing': buckets['embossing'],
                'roll': buckets['roll'],
                'sht': buckets['sht'],

                'wc_name': wo_list_sorted[0].workcenter_id.display_name,
            }

            days_map.setdefault(day, []).append(row)

            # Day / grand totals use FIRST-WO quantities
            grand_total_qty += qty_planned
            grand_total_remaining += qty_remaining

        # --------- Build per-day payload (pages + daily footers) ----------
        days_payload = []
        for day in sorted(days_map.keys()):
            rows = days_map[day]

            day_qty = sum(r['wo_yards'] for r in rows)
            day_rem = sum(r['remain_yd'] for r in rows)

            footer = {
                'embossings':      {'qty': 0.0, 'qty_s': '', 'count': 0},
                'rewind_slit_ins': {'qty': 0.0, 'qty_s': '', 'count': 0},
                'plating':         {'qty': 0.0, 'qty_s': '', 'count': 0},
                'sheeter_12':      {'qty': 0.0, 'qty_s': '', 'count': 0},
                'sheeter_3':       {'qty': 0.0, 'qty_s': '', 'count': 0},
                'sheeter_4':       {'qty': 0.0, 'qty_s': '', 'count': 0},
            }

            for r in rows:
                qty = r['wo_yards']

                # Embossings: any embossing cells on this MO
                if r['embossing']:
                    footer['embossings']['qty'] += qty
                    footer['embossings']['count'] += len(r['embossing'])

                # Rewind / Slit / Inspection:
                # >>> ONLY roll (NOT ctr, NOT sheeter) as you requested
                if r['roll']:
                    footer['rewind_slit_ins']['qty'] += qty
                    footer['rewind_slit_ins']['count'] += len(r['roll'])

                # Plating
                if r['plt']:
                    footer['plating']['qty'] += qty
                    footer['plating']['count'] += len(r['plt'])

                # Sheeter buckets: split Sht labels into 1/2, 3, 4
                seen_sht_12 = set()
                seen_sht_3 = set()
                seen_sht_4 = set()

                for cell in r['sht']:
                    label = (cell.get('label') or '').upper()

                    if any(k in label for k in ('SH01', 'SH02', 'SHT1', 'SHT2')):
                        key = 'sheeter_12'
                        seen = seen_sht_12
                    elif any(k in label for k in ('SH03', 'SHT3')):
                        key = 'sheeter_3'
                        seen = seen_sht_3
                    elif any(k in label for k in ('SH04', 'SHT4')):
                        key = 'sheeter_4'
                        seen = seen_sht_4
                    else:
                        key = 'sheeter_12'
                        seen = seen_sht_12

                    if label and label not in seen:
                        footer[key]['qty'] += qty
                        footer[key]['count'] += 1
                        seen.add(label)

            for key, val in footer.items():
                val['qty_s'] = self._fmt(val['qty'], digits=0)

            days_payload.append({
                'date': day,
                'rows': rows,
                'day_total_qty': day_qty,
                'day_total_qty_s': self._fmt(day_qty, digits=2),
                'day_total_remaining': day_rem,
                'day_total_remaining_s': self._fmt(day_rem, digits=2),
                'footer': footer,
            })

        # --------- Build per-week summary (with embossing by operation) ----------
        week_buckets = {}   # {(year, week): {...}}

        for dayblk in days_payload:
            day = dayblk['date']
            iso_year, iso_week, _iso_wday = day.isocalendar()
            wk_key = (iso_year, iso_week)

            wb = week_buckets.setdefault(wk_key, {
                'year': iso_year,
                'week': iso_week,
                'date_from': day,
                'date_to': day,
                'totals': {
                    'embossings':      {'qty': 0.0, 'count': 0},
                    'rewind_slit_ins': {'qty': 0.0, 'count': 0},
                    'plating':         {'qty': 0.0, 'count': 0},
                    'sheeter_12':      {'qty': 0.0, 'count': 0},
                    'sheeter_3':       {'qty': 0.0, 'count': 0},
                    'sheeter_4':       {'qty': 0.0, 'count': 0},
                },
                # embossing operations grouped by operation name
                'emb_ops': {},  # {label: {'qty':..., 'count':...}}
                # day blocks belonging to this week, in date order
                'day_blocks': [],
            })

            wb['day_blocks'].append(dayblk)

            # extend week date range
            if day < wb['date_from']:
                wb['date_from'] = day
            if day > wb['date_to']:
                wb['date_to'] = day

            # accumulate from day footer for totals
            for key in wb['totals'].keys():
                daily = dayblk['footer'][key]
                wb['totals'][key]['qty'] += daily['qty']
                wb['totals'][key]['count'] += daily['count']

            # ----- embossing by operation (left group of weekly summary) -----
            for r in dayblk['rows']:
                qty = r['wo_yards']
                for cell in r['embossing']:
                    label = (cell.get('label') or '').strip()
                    if not label:
                        continue
                    op = wb['emb_ops'].setdefault(label, {'qty': 0.0, 'count': 0})
                    op['qty'] += qty
                    op['count'] += 1

        weekly_summary = []
        for (year, week) in sorted(week_buckets.keys()):
            wb = week_buckets[(year, week)]

            # format totals
            totals_fmt = {}
            for key, val in wb['totals'].items():
                totals_fmt[key] = {
                    'qty': val['qty'],
                    'qty_s': self._fmt(val['qty'], digits=0),
                    'count': val['count'],
                }

            # format embossing operations list
            emb_ops_list = []
            for label in sorted(wb['emb_ops'].keys()):
                val = wb['emb_ops'][label]
                emb_ops_list.append({
                    'name': label,
                    'qty': val['qty'],
                    'qty_s': self._fmt(val['qty'], digits=0),
                    'count': val['count'],
                })

            weekly_summary.append({
                'year': year,
                'week': week,
                'week_date_from': wb['date_from'],
                'week_date_to': wb['date_to'],
                'totals': totals_fmt,
                'emb_ops': emb_ops_list,
                'days': wb['day_blocks'],
            })

        return {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'days': days_payload,
            'weekly_summary': weekly_summary,
            'grand_total_qty': grand_total_qty,
            'grand_total_remaining': grand_total_remaining,
            'company': self.env.company,
        }

    # ---------------- Actions ----------------

    def action_print_pdf(self):
        return self.env.ref(
            'mrp_workorder_schedule_report.action_report_mrp_workorder_schedule'
        ).report_action(self)
