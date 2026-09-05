# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from datetime import datetime, date, timedelta
import logging

_logger = logging.getLogger(__name__)



class MrpWorkCenterCapacity(models.Model):
    _name = "mrp.workcenter.capacity"
    _description = "Work Center Capacity"
    _order = "date_planned DESC"


    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    workorder_id = fields.Many2one('mrp.workorder', 'WorkOrder')
    production_id = fields.Many2one("mrp.production", 'Manufacturing Order', related='workorder_id.production_id')
    product_id = fields.Many2one("product.product", "Product")
    product_qty = fields.Float("Required Quantity")
    available_capacity_yards = fields.Float("Available Yards Capacity")
    product_uom_id = fields.Many2one('uom.uom', 'Unit of Measure')
    date_planned = fields.Datetime('Planned Date')
    week_nro = fields.Char('Week Number', compute='_get_week_number', store=True)
    active = fields.Boolean(default=True)
    wc_available_capacity_cal_yards = fields.Float(
        'WC Weekly Available Capacity(Yards)',
        related='workorder_id.qty_output_wo',
        store=True,
        readonly=True,
    )
    wc_available_capacity_cal_yards_display = fields.Float(
        'WC Weekly Available Capacity Display (Yards)',
        related='workorder_id.qty_output_wo',
        store=True,
        readonly=True,
    )
    wc_available_capacity_cal = fields.Float(
        'WC Weekly Available Capacity',
        compute='_calculate_wc_available_capacity_cal',
        store=True,
        group_operator="min",
    )
    wo_capacity_requirements = fields.Float('WO Capacity Requirements')
    wc_capacity_load = fields.Float('WC Capacity Load %', compute='_get_wc_capacity', store=True, group_operator="avg")
    wc_remaining_capacity = fields.Float('WC Remaining Capacity', compute='_get_wc_capacity', store=True)

    is_current_year = fields.Boolean(
        string="In Current Year",
        compute="_compute_year_flags",
        store=True,
        index=True,
    )
    is_next_year = fields.Boolean(
        string="In Next Year",
        compute="_compute_year_flags",
        store=True,
        index=True,
    )

    @api.depends('date_planned')
    def _compute_year_flags(self):
        """
        Why: Avoid client-side domain evaluation on dynamic dates.
        """
        for rec in self:
            rec.is_current_year = False
            rec.is_next_year = False
            if not rec.date_planned:
                continue

            # Use user timezone to decide the calendar year bucket
            user_dt = fields.Datetime.context_timestamp(rec, rec.date_planned)
            yr = user_dt.year

            # Current "today" in user TZ
            today_user = fields.Datetime.context_timestamp(rec, fields.Datetime.now())
            cur = today_user.year

            rec.is_current_year = (yr == cur)
            rec.is_next_year = (yr == cur + 1)
            

    @api.depends('week_nro')
    def _calculate_wc_available_capacity_cal(self):
        for record in self:
            week = record.week_nro
            _logger.info(" Record ID: %s | WEEK: %s", record.id, week)

            monday = datetime.strptime(week + '-1', "%Y-%W-%w") - timedelta(days=7)
            sunday = monday + timedelta(days=7)
            _logger.info("   Week Range: %s → %s", monday, sunday)

            nro_hours = record.workcenter_id.resource_calendar_id.get_work_hours_count(monday, sunday)
            _logger.info("   Work Hours in Calendar: %s", nro_hours)

            record.wc_available_capacity_cal = (
                nro_hours
                * record.workcenter_id.capacity
                * record.workcenter_id.time_efficiency
                / 100
            )
            _logger.info(
                "   Calculated wc_available_capacity_cal = %s (Capacity=%s, Efficiency=%s)",
                record.wc_available_capacity_cal,
                record.workcenter_id.capacity,
                record.workcenter_id.time_efficiency,
            )

        return True


    @api.depends('wo_capacity_requirements', 'wc_available_capacity_cal')
    def _get_wc_capacity(self):
        for record in self:
            _logger.info("➡️ Record ID: %s | Calculating Workcenter Capacity", record.id)
            _logger.info(
                "   Input Values → wo_capacity_requirements=%s | wc_available_capacity_cal=%s | available_capacity_yards=%s",
                record.wo_capacity_requirements,
                record.wc_available_capacity_cal,
                record.available_capacity_yards,
            )

            if record.wc_available_capacity_cal:
                record.wc_capacity_load = (
                    record.wo_capacity_requirements / record.wc_available_capacity_cal
                ) * 100
            else:
                record.wc_capacity_load = 0.0

            record.wc_remaining_capacity = (
                record.wc_available_capacity_cal - record.wo_capacity_requirements
            )

            _logger.info(
                "   Results → Load=%.2f%% | Remaining=%.2f | Yards=%.2f | YardDisplay=%.2f",
                record.wc_capacity_load,
                record.wc_remaining_capacity,
                record.wc_available_capacity_cal_yards,
                record.wc_available_capacity_cal_yards_display,
            )

        return True


    # @api.depends('week_nro')
    # def _calculate_wc_available_capacity_cal(self):
    #     for record in self:
    #         week = record.week_nro
    #         _logger.info("WEEK'%s'",week)
    #         monday = datetime.strptime(week + '-1', "%Y-%W-%w") - timedelta(days = 7)
    #         sunday = monday + timedelta(days = 7)
    #         nro_hours = record.workcenter_id.resource_calendar_id.get_work_hours_count(monday, sunday)
    #         record.wc_available_capacity_cal = nro_hours * record.workcenter_id.capacity * record.workcenter_id.time_efficiency / 100

    #     return True

    # @api.depends('wo_capacity_requirements','wc_available_capacity_cal')
    # def _get_wc_capacity(self):
    #     for record in self:
    #         if record.wc_available_capacity_cal:
    #             record.wc_capacity_load = (record.wo_capacity_requirements / record.wc_available_capacity_cal) * 100
    #         else:
    #             record.wc_capacity_load = 0.0
    #         record.wc_remaining_capacity = record.wc_available_capacity_cal - record.wo_capacity_requirements
    #         if record.available_capacity_yards > 0.00:
    #             record.wc_available_capacity_cal_yards = record.wc_remaining_capacity * record.available_capacity_yards
    #             record.wc_available_capacity_cal_yards_display = record.wc_remaining_capacity * record.available_capacity_yards
    #         else:
    #             record.wc_available_capacity_cal_yards = 0.00
    #             record.wc_available_capacity_cal_yards_display = record.wc_available_capacity_cal_yards
    #     return True

    @api.depends('date_planned')
    def _get_week_number(self):
        for record in self:
            week = record.date_planned.date().strftime("%V")
            year = record.date_planned.date().strftime("%Y")
            record.week_nro = year + "-" + week
        return True
