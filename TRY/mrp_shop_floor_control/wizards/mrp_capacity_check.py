# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, timedelta
import calendar
import logging

_logger = logging.getLogger(__name__)

class MrpCapacityCheck(models.TransientModel):
    _name = "mrp.capacity.check"
    _description = 'MRP Capacity Check'


    def _default_production_id(self):
        return self.env['mrp.production'].browse(self.env.context.get('active_id'))

    def _default_current_week_year(self):
        current_date = fields.Datetime.now()
        year, week, _ = current_date.isocalendar()
        return f"{year}-{week:02d}"

    production_id = fields.Many2one("mrp.production", 'Manufacturing Order', default=lambda self: self._default_production_id(), readonly=True)
    capacity_item_ids = fields.One2many('mrp.capacity.check.item', 'check_id', string="Capacity Items", readonly=True)
    capacity_item_all_ids = fields.One2many('mrp.capacity.check.allitem', 'check_id', string="Capacity Items", readonly=True)
    capacity_item_empty_ids = fields.One2many('mrp.capacity.check.emptyweeks', 'check_id', string="Avl Capacity Items", readonly=True)
    current_week_year = fields.Char(string="Current Week-Year", default=lambda self: self._default_current_week_year(), readonly=True)

    @api.onchange('production_id')
    def get_records(self):
        workcenters = self.env['mrp.workcenter'].search([('id', 'in', self.production_id.workorder_ids.workcenter_id.ids)])
        result = {wc: {} for wc in workcenters.ids}
        result_all = {wc: {} for wc in workcenters.ids}
        domain = [('production_id', '=', self.production_id.id)]

        domain_all = [('workcenter_id', 'in', workcenters.ids)]
        res = self.env["mrp.workcenter.capacity"].read_group(domain,
            ['workcenter_id', 'week_nro', 'wo_capacity_requirements'], ['workcenter_id', 'week_nro'],
            lazy=False)
        for res_group in res:
            result[res_group['workcenter_id'][0]][res_group['week_nro']] = res_group['wo_capacity_requirements']
        _logger.info("RESULTTTTTT '%s'", result)

        # Define the range of weeks (assuming a year, change as needed)
        current_date = datetime.now()
        current_year, current_week = current_date.isocalendar()[:2]
        start_week = max(current_week - 4, 1)  # Ensure the week doesn't go below 1
        weeks_set = {f"{current_year}-{str(week).zfill(2)}" for week in range(start_week, 53)}

        if current_date.month == 12:
            next_month_year = current_date.year + 1
            next_month = 1
            days_in_month = calendar.monthrange(next_month_year, next_month)[1]
            for day in range(1, days_in_month + 1):
                iso_year, iso_week, _ = date(next_month_year, next_month, day).isocalendar()
                if iso_year == next_month_year:
                    weeks_set.add(f"{iso_year}-{str(iso_week).zfill(2)}")

        weeks = sorted(weeks_set)

        for workcenter in workcenters:
            for week, req in result[workcenter.id].items():
                id_created_item = self.env['mrp.capacity.check.item'].create({
                    'workcenter_id': workcenter.id,
                    'week_nro': week,
                    'wo_capacity_requirements': req,
                    'check_id': self.id,
                })

        res_all = self.env["mrp.workcenter.capacity"].read_group(domain_all,
            ['workcenter_id', 'week_nro', 'wo_capacity_requirements'], ['workcenter_id', 'week_nro'],
            lazy=False)
        for res_group_all in res_all:
            result_all[res_group_all['workcenter_id'][0]][res_group_all['week_nro']] = res_group_all['wo_capacity_requirements']

        for workcenter in workcenters:
            for week in weeks:
                req = result_all[workcenter.id].get(week, 0)  # Default to 0 if no data
                id_created_allitem = self.env['mrp.capacity.check.allitem'].create({
                    'workcenter_id': workcenter.id,
                    'week_nro': week,
                    'wo_capacity_requirements': req,
                    'check_id': self.id,
                })
                item = self.env['mrp.capacity.check.item'].search([('workcenter_id', '=', workcenter.id), ('week_nro', '=', week)])
                _logger.info("ITEMMMMMM '%s'", item)
                if item:
                    id_created_allitem.indicator = True

        return self._reopen_form()


    # @api.onchange('production_id')
    # def get_records(self):
    #     workcenters = self.env['mrp.workcenter'].search([('id', 'in', self.production_id.workorder_ids.workcenter_id.ids)])
    #     result = {wc: {} for wc in workcenters.ids}
    #     result_all = {wc: {} for wc in workcenters.ids}
    #     domain = [('production_id', '=', self.production_id.id)]

    #     domain_all = [('workcenter_id', 'in', workcenters.ids)]
    #     res = self.env["mrp.workcenter.capacity"].read_group(domain,
    #         ['workcenter_id', 'week_nro', 'wo_capacity_requirements'], ['workcenter_id', 'week_nro'],
    #         lazy=False)
    #     for res_group in res:
    #         result[res_group['workcenter_id'][0]][res_group['week_nro']] = res_group['wo_capacity_requirements']
    #     _logger.info("RESULTTTTTT '%s'",result)
        # for workcenter in workcenters:
        #     for week, req in result[workcenter.id].items():
        #         id_created_item = self.env['mrp.capacity.check.item'].create({
        #             'workcenter_id': workcenter.id,
        #             'week_nro': week,
        #             'wo_capacity_requirements': req,
        #             'check_id': self.id,
        #         })
    #     res_all = self.env["mrp.workcenter.capacity"].read_group(domain_all,
    #         ['workcenter_id', 'week_nro', 'wo_capacity_requirements'], ['workcenter_id', 'week_nro'],
    #         lazy=False)
    #     for res_group_all in res_all:
    #         result_all[res_group_all['workcenter_id'][0]][res_group_all['week_nro']] = res_group_all['wo_capacity_requirements']
    #     for workcenter in workcenters:
    #         for week, req in result_all[workcenter.id].items():
    #             id_created_allitem = self.env['mrp.capacity.check.allitem'].create({
    #                 'workcenter_id': workcenter.id,
    #                 'week_nro': week,
    #                 'wo_capacity_requirements': req,
    #                 'check_id': self.id,
    #             })
    #             item = self.env['mrp.capacity.check.item'].search([('workcenter_id', '=', workcenter.id),('week_nro', '=', week)])
    #             _logger.info("ITEMMMMMM '%s'",item)
    #             if item:
    #                 id_created_allitem.indicator = True
    #     return self._reopen_form()
    def _reopen_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new'}


class MrpCapacityCheckItem(models.TransientModel):
    _name = "mrp.capacity.check.item"
    _description = 'MRP Capacity Check Item'

    check_id = fields.Many2one('mrp.capacity.check', readonly=True)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    week_nro = fields.Char('Week Number')
    wo_capacity_requirements = fields.Float('WO Capacity Requirements (Hours)')
    wc_available_capacity_cal = fields.Float('WC Weekly Available Capacity', compute='_calculate_wc_available_capacity_cal', store=True)
    date_planned = fields.Datetime('Monday')

    @api.depends('week_nro')
    def _calculate_wc_available_capacity_cal(self):
        for record in self:
            week = record.week_nro
            monday = datetime.strptime(week + '-1', "%Y-%W-%w") - timedelta(days = 7)
            sunday = monday + timedelta(days = 7)
            nro_hours = record.workcenter_id.resource_calendar_id.get_work_hours_count(monday, sunday)
            record.wc_available_capacity_cal = nro_hours * record.workcenter_id.capacity * record.workcenter_id.time_efficiency / 100
            record.date_planned = monday
        return True

class MrpCapacityCheckAllItem(models.TransientModel):
    _name = "mrp.capacity.check.allitem"
    _description = 'MRP Capacity Check Item'

    check_id = fields.Many2one('mrp.capacity.check', readonly=True)
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    week_nro = fields.Char('Week Number')
    wo_capacity_requirements = fields.Float('WO Capacity Requirements (Hours)')
    wc_available_capacity_cal = fields.Float('WC Weekly Available Capacity', compute='_calculate_wc_available_capacity_cal', store=True)
    wc_capacity_load = fields.Float('WC Capacity Load %', compute='_get_wc_capacity')
    wc_remaining_capacity = fields.Float('WC Remaining Capacity', compute='_wc_capacity')
    indicator = fields.Boolean(default=False)


    @api.depends('week_nro')
    def _calculate_wc_available_capacity_cal(self):
        for record in self:
            week = record.week_nro
            monday = datetime.strptime(week + '-1', "%Y-%W-%w") - timedelta(days = 7)
            sunday = monday + timedelta(days = 7)
            nro_hours = record.workcenter_id.resource_calendar_id.get_work_hours_count(monday, sunday)
            record.wc_available_capacity_cal = nro_hours * record.workcenter_id.capacity * record.workcenter_id.time_efficiency / 100
        return True

    @api.depends('wo_capacity_requirements','wc_available_capacity_cal')
    def _get_wc_capacity(self):
        for record in self:
            if record.wc_available_capacity_cal:
                record.wc_capacity_load = (record.wo_capacity_requirements / record.wc_available_capacity_cal) * 100
            else:
                record.wc_capacity_load = 0.0
            record.wc_remaining_capacity = record.wc_available_capacity_cal - record.wo_capacity_requirements
        return True

    def open_pivot_info(self):
        context={'default_workcenter_id': self.workcenter_id.id,}
        domain = [("workcenter_id", "=", self.workcenter_id.id)]
        return {
            "name": _("Workcenter Capacity Evaluations"),
            "view_mode": "pivot",
            "res_model": "mrp.workcenter.capacity",
            "type": "ir.actions.act_window",
            "context": context,
            "domain": domain,
            "target": "fullscreen",
        }

class MrpCapacityCheckEmptyWeeks(models.TransientModel):
    _name = 'mrp.capacity.check.emptyweeks'
    _description = 'Empty Weeks for Workcenters'

    workcenter_id = fields.Many2one('mrp.workcenter', string='Workcenter', required=True)
    week_nro = fields.Integer(string='Week Number', required=True)
    check_id = fields.Many2one('mrp.capacity.check', string='Check', required=True)




