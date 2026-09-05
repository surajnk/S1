from odoo import api, fields, models, _
import datetime
from functools import reduce
import numpy as np
from dateutil.relativedelta import relativedelta
import math


class MrpWorkcenterCapacityReport(models.Model):
    _name = 'mrp.workcenter.capacity.report'
    _description = 'MRP Workcenter Capacity Report'

    @api.model
    def get_str_to_date(self, date):
        """
        Get String To Date
        :param date:
        :return:
        """
        return datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')

    def getDateRangeFromWeek(self, p_year, p_week):
        firstdayofweek = datetime.datetime.strptime(f'{p_year}-W{int(p_week) - 1}-1', "%Y-W%W-%w").date()
        lastdayofweek = firstdayofweek + datetime.timedelta(days=6.9)
        current_week = False
        if firstdayofweek <= datetime.datetime.now().date() <= lastdayofweek:
            current_week = True
        return firstdayofweek, lastdayofweek, current_week

    @api.model
    def get_order_start_date(self, order_start_date, operation_name=''):
        """
        :param date_order_start:
        :return:
        """
        if order_start_date and operation_name == 'prev':
            return self.get_str_to_date(order_start_date) - relativedelta(days=7)
        if order_start_date and operation_name == 'next':
            return self.get_str_to_date(order_start_date) + relativedelta(days=7)
        if order_start_date and not operation_name:
            return self.get_str_to_date(order_start_date)
        return datetime.datetime.now()

    @api.model
    def get_titles(self, order_start_date=False, order_end_date=False):
        """
        :return:
        """
        titles = ['Work Center', 'M/O', 'Work Order', 'Sequence', 'Scheduled Date']
        weeks_title = []
        if order_start_date:
            start_date = self.get_str_to_date(order_start_date)
            if not order_end_date:
                year, week_number, day_of_week = start_date.isocalendar()
                for x in [1]:
                    if week_number == 52:
                        week_number = 0
                        year = year + 1
                    week_number += 1
                    fw, lw, is_current_week = self.getDateRangeFromWeek(year, week_number)
                    week_name = 'Week ' + str(week_number)
                    weeks_title.append({
                        'week_name': week_name, 's_date': fw, 'e_date': lw, 'is_current_week': is_current_week})
            else:
                end_date = self.get_str_to_date(order_end_date)
                weeks_title.append({
                    'week_name': 'XX', 's_date': start_date.date(), 'e_date': end_date.date(),
                    'is_current_week': False})
        return {'titles': titles, 'weeks_title': weeks_title}

    @api.model
    def get_work_order_titles(self):
        titles = ['Work Order', 'Work Center', 'M/O', 'Product', 'Scheduled Date', 'Elapsed', 'Overall Duration',
                  'WO Quantities']
        return {'titles': titles}

    @api.model
    def get_datas(self, order_start_date, order_end_date=False):
        """
        :param order_start_date:
        :param po_ids:
        :return:
        """
        work_center_rec = self.env['mrp.workcenter'].search([])
        titles = self.get_titles(order_start_date, order_end_date)
        main_data = []
        for wc_rec in work_center_rec:
            word_center_data = []
            wc_available_capacity_cal = 0
            wc_capacity = 0
            work_order_line = []
            for wo_rec in self.env['mrp.workorder'].search([
                ('state', 'not in', ['done', 'cancel']), ('workcenter_id', '=', wc_rec.id)]):
                wo_capacity_requirements = 0
                for week_title in titles.get('weeks_title'):
                    if not wc_capacity:
                        sd = week_title.get('s_date')
                        ed = week_title.get('e_date')
                        s_date = datetime.datetime(year=sd.year, month=sd.month, day=sd.day)
                        e_date = datetime.datetime(year=ed.year, month=ed.month, day=ed.day)
                        nro_hours = wc_rec.resource_calendar_id.get_work_hours_count(s_date, e_date)
                        wc_available_capacity_cal = nro_hours * wc_rec.capacity * wc_rec.time_efficiency / 100
                        wc_capacity = nro_hours
                    if wo_rec.date_planned_start_wo and week_title.get('s_date') <= \
                            wo_rec.date_planned_start_wo.date() <= week_title.get('e_date'):
                        wo_capacity_requirements = round(wo_rec.wo_capacity_requirements, 2)
                        wc_remaining_capacity = wc_available_capacity_cal - wo_capacity_requirements
                        wc_capacity_load = (wo_capacity_requirements / wc_available_capacity_cal) * 100
                        wc_weekly_available_capacity_yard = 0
                        if wc_available_capacity_cal > 0.00:
                            wc_weekly_available_capacity_yard = wc_remaining_capacity * wc_available_capacity_cal
                        work_order_line.append({
                            'work_order_id': wo_rec.id,
                            'work_order_name': wo_rec.name,
                            'work_order_sequence': wo_rec.sequence or '',
                            'work_order_planned_date': wo_rec.date_planned_start_wo,
                            'wc_available_capacity_cal': round(wc_available_capacity_cal, 2),
                            'wo_capacity_requirements': wo_capacity_requirements,
                            'wc_capacity_load': round(wc_capacity_load, 2),
                            'wc_weekly_available_capacity_yard': round(wc_weekly_available_capacity_yard, 2),
                            'wc_remaining_capacity': round(wc_remaining_capacity, 2),
                            'manufacturing': wo_rec.production_id and wo_rec.production_id.name or '',
                        })
                        wc_available_capacity_cal = wc_remaining_capacity
            word_center_data.append({
                'work_center_id': wc_rec.id,
                'work_center_name': wc_rec.name,
                'wc_capacity': wc_capacity,
                'work_order_line': work_order_line,
                'show_record': True if work_order_line else False,
            })
            main_data.append(word_center_data)
        return main_data

        # work_order_rec = self.env['mrp.workorder'].search([('state', 'not in', ['done', 'cancel'])])
        # titles = self.get_titles(order_start_date)
        # main_data = []
        # for po_rec in po_records:
        #     po_line_data = []
        #     po_data = []
        #     total_order_qty = 0
        #     total_received_qty = 0
        #     po_week_data = []
        #     for po_line in po_rec.order_line:
        #         week_data = []
        #         po_wk_data = []
        #         for week_title in titles.get('weeks_title'):
        #             wk_data = self.get_week_data(week_title.get('s_date'), week_title.get('e_date'), po_line)
        #             week_data.append(wk_data)
        #             po_wk_data.append(wk_data[0])
        #         po_line_data.append({
        #             'main_line': False,
        #             'po_name': po_rec.name,
        #             'po_id': po_rec.id,
        #             'product_name': po_line.product_id.name,
        #             'product_id': po_line.product_id.id,
        #             'order_qty': po_line.product_qty,
        #             'received_qty': po_line.qty_received,
        #             'week_data': week_data,
        #             'total_order_qty': 0.00,
        #             'total_received_qty': 0.00,
        #         })
        #         total_order_qty += po_line.product_qty
        #         total_received_qty += po_line.qty_received
        #         po_week_data.append(po_wk_data)
        #     week_data_po = self.compute_po_week_data(po_week_data)
        #     po_data.append({
        #         'main_line': True,
        #         'po_name': po_rec.name,
        #         'po_id': po_rec.id,
        #         'total_order_qty': total_order_qty,
        #         'total_received_qty': total_received_qty,
        #         'week_data': week_data_po,
        #         'po_line': po_line_data
        #     })
        #     main_data.append(po_data)
        # return main_data

    @api.model
    def get_workorder_datas(self, order_start_date, order_end_date=False, manufacturing_order=False):
        domain = []
        wo_domain = []
        if order_start_date:
            start_datetime = fields.Datetime.to_datetime(order_start_date)
            domain += [('x_mrp_confirmed_date', '>=', start_datetime.date() if start_datetime else order_start_date)]
            wo_domain += [('date_planned_start_wo', '>=', start_datetime or order_start_date)]
        if order_end_date:
            end_datetime = fields.Datetime.to_datetime(order_end_date)
            domain += [('x_mrp_confirmed_date', '<', end_datetime.date() if end_datetime else order_end_date)]
            wo_domain += [('date_planned_start_wo', '<', end_datetime or order_end_date)]
        if manufacturing_order:
            domain += [('product_id', '=', manufacturing_order)]
            wo_domain += [('product_id', '=', manufacturing_order)]

        manufacturing_ids = self.env['mrp.production']

        source_manu = manufacturing_ids.filtered(lambda r: r.origin)
        source_manu_ids = source_manu.search(wo_domain)

        not_source_manu = manufacturing_ids.filtered(lambda r: not r.origin)
        no_source_manu_ids = not_source_manu.search(domain)

        main_data = []
        for mo in source_manu_ids:
            for wo in mo.workorder_ids:
                work_order_data = []
                work_order_data.append({
                    'work_order_name': wo.workcenter_id.name,
                    'mo_name': wo.production_id.name,
                    'product': wo.production_id.product_id.name,
                    'date': wo.date_planned_start_wo,
                    'elapsed': self.float_to_time(wo.duration),
                    'ovarall_duration': self.float_to_time(wo.overall_duration),
                    'qo_quantities': wo.qty_output_wo,
                    'workorder_name': wo.name,
                })
                main_data.append(work_order_data)
        for mo in no_source_manu_ids:
            for wo in mo.workorder_ids:
                work_order_data = []
                work_order_data.append({
                    'work_order_name': wo.workcenter_id.name,
                    'mo_name': wo.production_id.name,
                    'product': wo.production_id.product_id.name,
                    'date': wo.date_planned_start_wo,
                    'elapsed': self.float_to_time(wo.duration),
                    'ovarall_duration': self.float_to_time(wo.overall_duration),
                    'qo_quantities': wo.qty_output_wo,
                    'workorder_name': wo.name,
                })
                main_data.append(work_order_data)

        return main_data

    def float_to_time(self, time_float):
        hours = int(time_float)
        minutes = math.ceil((time_float - hours) * 60)
        return '%02d:%02d' % (hours, minutes)
