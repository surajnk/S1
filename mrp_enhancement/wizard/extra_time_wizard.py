from datetime import datetime
from odoo import models, fields, api, _


class ExtraTimeLine(models.Model):
    _name = 'extra.time.line'

    date_start = fields.Datetime(string='Start Date')
    date_end = fields.Datetime(string='End Date', readonly=1)
    timer_duration = fields.Float(invisible=1, string='Time Duration (Minutes)')
    time_id = fields.Many2one('extra.time')
    unit_amount = fields.Float()


class ExtraTime(models.Model):
    _name = "extra.time"
    _description = "Extra time need to be added"
    _rec_name = "workorder_id"

    @api.model
    def default_get(self, default_fields):
        res = super(ExtraTime, self).default_get(default_fields)
        if self._context.get('active_id'):
            res['workorder_id'] = self._context.get('active_id')
        return res

    workorder_id = fields.Many2one('mrp.workorder', string='Work Order')
    setup_time = fields.Float(string='Setup time', compute='_compute_duration')
    task_timer = fields.Boolean(string='Timer', default=False)
    is_user_working = fields.Boolean(
        'Is Current User Working', compute='_compute_is_user_working')
    extra_line_id = fields.One2many('extra.time.line', 'time_id')
    current_setupime = fields.Float()

    @api.depends('extra_line_id.timer_duration')
    def _compute_duration(self):
        for record in self:
            record.setup_time = sum(record.extra_line_id.mapped('timer_duration'))

    def _compute_is_user_working(self):
        """ Checks whether the current user is working """
        for order in self:
            if order.extra_line_id.filtered(lambda x: (not x.date_end)):
                order.is_user_working = True
            else:
                order.is_user_working = False

    @api.model
    @api.constrains('task_timer')
    def toggle_start(self):
        if self.task_timer is True:
            self.write({'is_user_working': True})
            time_line = self.env['extra.time.line']
            for time_sheet in self:
                time_line.create({
                    'time_id': time_sheet.id,
                    'date_start': datetime.now(),
                })
        else:
            self.write({'is_user_working': False})
            time_line_obj = self.env['extra.time.line']
            domain = [('time_id', '=', self.id), ('date_end', '=', False)]
            for time_line in time_line_obj.search(domain):
                time_line.write({'date_end': fields.Datetime.now()})
                if time_line.date_end:
                    diff = fields.Datetime.from_string(time_line.date_end) - fields.Datetime.from_string(
                        time_line.date_start)
                    time_line.timer_duration = round(diff.total_seconds() / 60.0, 2)
                    time_line.unit_amount = round(diff.total_seconds() / (60.0 * 60.0), 2)
                else:
                    time_line.unit_amount = 0.0
                    time_line.timer_duration = 0.0

    def start_timere(self):
        if not self.task_timer:
            self.write({'task_timer': True})
            self.current_setupime = self.setup_time
            self.workorder_id.timer_id = self.id
        return {
            'name': _('Enter time'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'extra.time',
            'view_id': self.env.ref(
                'mrp_enhancement.extra_time_form_view').id,
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,  # FIX: preserve from_start/from_done
        }
    # def start_timere(self):
    #     if not self.task_timer:
    #         self.write({'task_timer': True})
    #         self.current_setupime = self.setup_time
    #         self.workorder_id.timer_id = self.id
    #     return {
    #         'name': _('Enter time'),
    #         'type': 'ir.actions.act_window',
    #         'view_mode': 'form',
    #         'res_model': 'extra.time',
    #         'view_id': self.env.ref(
    #             'mrp_enhancement.extra_time_form_view').id,
    #         'res_id': self.id,
    #         'target': 'new'
    #     }

    def action_skip(self):
        self.write({'task_timer': False})
        self.setup_time = 0
        self.workorder_id.setup_time = self.setup_time
        if self.workorder_id.state in ('ready', 'pending', 'progress'):  # FIX: guard against pending state
            self.workorder_id.button_start()
    # def action_skip(self):
    #     # self.workorder_id.button_finish()
    #     self.write({'task_timer': False})
    #     self.setup_time = 0
    #     self.workorder_id.setup_time = self.setup_time
    #     self.workorder_id.button_start()

    def add_time(self):
        if self._context.get('from_done'):
            # if not self.workorder_id.cleanup_time:
            #     self.workorder_id.cleanup_time = self.cleanup_time
            self.workorder_id.button_finish()
            # self.workorder_id.time_ids
        if self._context.get('from_start'):
            self.write({'task_timer': False})
            self.workorder_id.setup_time = self.setup_time
            self.workorder_id.button_start()

            time_id = self.env['mrp.workcenter.productivity'].search(
                [('workorder_id', '=', self.workorder_id.id), ('date_end', '=', False)], limit=1)

            time_id.setup_duration = self.setup_time - self.current_setupime
