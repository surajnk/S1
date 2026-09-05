from odoo import api, fields, models, _
import datetime
from pytz import timezone, utc


class WcReportChangeDateWiz(models.TransientModel):
    _name = 'wc.report.change.date.wiz'
    _description = 'Wc Report Change Date Wiz'

    def _default_start(self):
        tz = timezone(self.env.user.tz or 'UTC')
        # Get today's date in the USER's local timezone
        now_local = datetime.datetime.now(tz)
        today_local = now_local.date()
        local_start = tz.localize(datetime.datetime.combine(today_local, datetime.time.min))
        return local_start.astimezone(utc).replace(tzinfo=None)

    def _default_end(self):
        tz = timezone(self.env.user.tz or 'UTC')
        now_local = datetime.datetime.now(tz)
        today_local = now_local.date()
        local_end = tz.localize(datetime.datetime.combine(today_local, datetime.time(23, 59, 59)))
        return local_end.astimezone(utc).replace(tzinfo=None)

    start_date = fields.Datetime('Date', required=1, default=_default_start)
    end_date = fields.Datetime('Date', required=1, default=_default_end)

    def action_wc_report_with_start_date(self):
        """
        :return:
        """
        return {
            'name': 'Workcenter Capacity Report',
            'type': 'ir.actions.client',
            'tag': 'mrp_workcenter_capacity_report',
            'context': {'order_start_date': self.start_date, 'order_end_date': self.end_date}
        }


class WoReportWizard(models.TransientModel):
    _name = 'wo.report.wiz'

    start_date = fields.Datetime('Start Date', default=datetime.datetime.today().date())
    end_date = fields.Datetime('End Date', default=datetime.datetime.today().date())
    manufacture_id = fields.Many2one('mrp.production','Manufacture')
    product_id = fields.Many2one('product.product',string="Product")

    def action_show_report(self):
        return {
            'name': 'Work Order Report',
            'type': 'ir.actions.client',
            'tag': 'mrp_workorder_report',
            'context': {'order_start_date': self.start_date, 'order_end_date': self.end_date,
                        'manufacturing_order': self.product_id.id}
        }
