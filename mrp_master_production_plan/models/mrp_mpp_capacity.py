# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, time, timedelta


class MrpMPPCapacity(models.Model):
    _name = "mrp.mpp.capacity"
    _description = "Master Production Plan Capacity"
    _order = "date_planned DESC"

    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    duration = fields.Float(string='Capacity Load (Hours)')
    capacity = fields.Float('Weekly Capacity (Hours)', compute='_calculate_capacity', store=True)
    product_id = fields.Many2one("product.product", "Product")
    product_qty = fields.Float("Required Quantity")
    product_uom_id = fields.Many2one('uom.uom', 'UoM')
    date_planned = fields.Datetime('Planned Date')
    SOP_item = fields.Char('SOP Item Reference')
    MPP_item = fields.Char('MPP Item Reference')
    active = fields.Boolean(default=True)
    sop_duration = fields.Float('SOP Capacity Load (Hours)')


    @api.depends('date_planned')
    def _calculate_capacity(self):
        for record in self:
            weekday = record.date_planned.weekday()
            date_planned = record.date_planned.replace(minute=0, hour=0, second=0, microsecond=0)
            monday = date_planned - timedelta(days = weekday)
            sunday = date_planned + timedelta(days = 7 - weekday)
            nro_hours = record.workcenter_id.resource_calendar_id.get_work_hours_count(monday, sunday)
            record.capacity = nro_hours * record.workcenter_id.capacity * record.workcenter_id.time_efficiency / 100
        return True