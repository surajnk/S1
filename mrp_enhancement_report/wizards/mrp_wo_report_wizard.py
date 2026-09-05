# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
import logging
import math
from collections import defaultdict


_logger = logging.getLogger(__name__)

class MrpWoReportWizard(models.TransientModel):
    _name = "mrp.wo.report.wizard"
    _description = 'MRP WO Scheduling Wizard'

    start_date = fields.Datetime(string='Scheduled Start Date', required=1)
    end_date = fields.Datetime(string='Scheduled End Date', required=1)
    workcenter_ids = fields.Many2many('mrp.workcenter', required=1)

    def print_wo_report(self):
        domain = [('workcenter_id', 'in', self.workcenter_ids.ids), ('date_planned_start_wo', '>=', self.start_date),
                  ('date_planned_start_wo', '<=', self.end_date)]
        wc_name = []
        for wc_rec in self.workcenter_ids:
            workorder_ids = self.env['mrp.workorder'].search(
                [('workcenter_id', '=', wc_rec.id), ('date_planned_start_wo', '>=', self.start_date),
                 ('date_planned_start_wo', '<=', self.end_date)], order='date_planned_start_wo ASC')
            workorder_dict = {}
            i = 0
            date_data = {}
            for workorder_id in workorder_ids:
                if workorder_id.date_planned_start_wo.strftime('%Y-%m-%d') not in date_data:
                    date_data.update({workorder_id.date_planned_start_wo.strftime('%Y-%m-%d'): []})
                sale_id = workorder_id.production_id.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
                #_logger.info("DAYYYYY'%s'",workorder_id.date_planned_start_wo.strftime("%V"))
                workorder_data = {'date': workorder_id.date_planned_start_wo.strftime('%Y-%m-%d'),
                                  'W/O': workorder_id.workcenter_id.name,
                                  'M/O': workorder_id.production_id.name,
                                  'Shaded': 'Y' if workorder_id.shaded else '',
                                  'Due': workorder_id.production_id.x_mrp_confirmed_date,
                                  'Finished Part/ Stock': workorder_id.production_id.product_id.name,
                                  'Cust': sale_id[0].partner_id.ref if sale_id else "Stock Order",
                                  'Width/Trim': str(workorder_id.width) + '/' + str(workorder_id.trim),
                                  'W/O Qty': workorder_id.production_id.x_order_master_yards,
                                  'Cust Qty': workorder_id.production_id.product_qty,
                                  'Hrs': workorder_id.duration_expected_hrs,
                                  'Base Avail': workorder_id.base_avail,
                                  'T/C': workorder_id.t_c,
                                  'Rod': workorder_id.rod,
                                  'weekday' : workorder_id.date_planned_start_wo.strftime("%a"),
                                  'weeknumb' : workorder_id.date_planned_start_wo.strftime("%V")
                                  }
                date_data[workorder_id.date_planned_start_wo.strftime('%Y-%m-%d')].append(workorder_data)
            date_total = {}
            for date_data_val in date_data:
                date_total.update({date_data_val: sum([x['Hrs'] for x in date_data[date_data_val]])})
            wc_name.append({wc_rec.name: [date_data, date_total]})
            _logger.info("WC NAMMEEEEE'%s'",wc_name)
        data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'report_date': fields.date.today(),
            'report_time': fields.datetime.today().strftime("%H:%M:%S"),
            'workcenter_ids': self.workcenter_ids,
            'workorder_data': wc_name,
        }
        return self.env.ref('mrp_enhancement_report.report_workorder').report_action(self, data=data)


class MrpWcProdReportWizard(models.TransientModel):
    _name = "mrp.wc.prod.report.wizard"
    _description = 'MRP WC Production Wizard'

    start_date = fields.Datetime(string='Start Date', required=1)
    end_date = fields.Datetime(string='End Date', required=1)
    #workcenter_ids = fields.Many2many('mrp.workcenter', required=1)

    def print_wc_prod_report(self):
        worksheet_ids = self.env['mrp.workcenter.productivity'].search(
                [('date_start', '>=', self.start_date),
                 ('date_end', '<=', self.end_date)], order='date_start ASC')

        date_data = {}
        shift1_data = {}
        shift2_data = {}
        workorder_data = {}
        grouped_data = {}
        wcs_name = []
        setup_count = 0
        avgset = 0
        for workorder_id in worksheet_ids:
            workcenter = workorder_id.workcenter_id.name
            shift = workorder_id.x_shift_time.x_shift_name
            hours = (workorder_id.duration + workorder_id.setup_duration) / 60
            setupd = workorder_id.setup_duration
            yards = workorder_id.x_yards_out
            if hours:
                realized_yards = math.floor(yards / hours)
                _logger.info("REALIZEDDDDDD YDSSSSSS'%s'",realized_yards)
            if setupd:
                setup_count += 1
                avgset = setupd / setup_count
            _logger.info("SETUPP COUNTTT'%s'",setup_count)
            
            if workcenter not in grouped_data:
                grouped_data[workcenter] = {}
            if shift not in grouped_data[workcenter]:
                grouped_data[workcenter][shift] = {'Hours': 0, 'Yards': 0, 'Setup':0, 'Realized Yards': 0, 'SetupC':0, 'AvgSet':0, 'AYPM':0}
            
            # Sum the hours and yards for each shift
            grouped_data[workcenter][shift]['Hours'] += hours
            grouped_data[workcenter][shift]['Yards'] += yards
            grouped_data[workcenter][shift]['Setup'] += setupd
            grouped_data[workcenter][shift]['Realized Yards'] = int(grouped_data[workcenter][shift]['Yards'] / grouped_data[workcenter][shift]['Hours']) if grouped_data[workcenter][shift]['Hours'] != 0 else 1
            grouped_data[workcenter][shift]['SetupC'] += setup_count
            grouped_data[workcenter][shift]['AvgSet'] = (grouped_data[workcenter][shift]['Setup'] / grouped_data[workcenter][shift]['SetupC']) if grouped_data[workcenter][shift]['SetupC'] != 0 else 1 
            grouped_data[workcenter][shift]['AYPM'] = (grouped_data[workcenter][shift]['Hours'] - grouped_data[workcenter][shift]['Setup']) / 60 

        _logger.info("GROUPPEDD DATATAA'%s'",grouped_data)
        rowspan = defaultdict(int)

        for workcenter, shifts in grouped_data.items():
            for shift, data in shifts.items():
                wcs_name.append({
                    'Workcenter': workcenter,
                    'Shift': shift,
                    'Hours': data['Hours'],
                    'Setup': data['Setup'],
                    'SetupC': data['SetupC'],
                    'AvgSet': data['AvgSet'],
                    'AvgYPM': data['AYPM'],
                    'Yards': data['Yards'],
                    'Realized Yards':data['Realized Yards']
                })
        
        for record in wcs_name:
           rowspan[record['Workcenter']] += 1 if 'Shift' in record else 0
        _logger.info("WCCCCCSSSSS'%s'",wcs_name)
        
        line = {}
        for res in wcs_name:
            if line.get(res.get('Workcenter')):
                values = {
                    'Shift': res.get('Shift'),
                    'SetT': res.get('Setup'),
                    'SetCount': res.get('SetupC'),
                    'AvgSt': res.get('AvgSet'),
                    'AvgYm': res.get('AvgYPM'),
                    'Yds': res.get('Yards'),
                    'Hours': res.get('Hours'),
                    'RelYds': res.get('Realized Yards'),
                }
                line.get(res.get('Workcenter')).append(values)
            else:
                values = [{
                    'Shift': res.get('Shift'),
                    'SetT': res.get('Setup'),
                    'SetCount': res.get('SetupC'),
                    'AvgSt': res.get('AvgSet'),
                    'AvgYm': res.get('AvgYPM'),
                    'Yds': res.get('Yards'),
                    'Hours': res.get('Hours'),
                    'RelYds': res.get('Realized Yards'),
                }]
                line[res.get('Workcenter')] = values
        _logger.info("LLINEEEEEE'%s'",line)

        
        data = {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'group_data':wcs_name,
            'rowspan': rowspan,
            'line': line
        }
        return self.env.ref('mrp_enhancement_report.report_workcenter_prod').report_action(self, data=data)