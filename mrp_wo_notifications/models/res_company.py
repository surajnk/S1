# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    enable_wo_notifications = fields.Boolean(
        string='Enable WO notifications',
        help='Send email notifications when a workorder produces less than its planned quantity.',
    )
    wo_notification_timeframe = fields.Selection(
        selection=[
            ('last_week', 'Last 1 week Workorders'),
            ('last_two_weeks', 'Last 2 week Workorders'),
            ('last_month', 'Last 1 month Workorders'),
        ],
        string='WO notification range',
        default='last_week',
        help='Limit notifications to workorders created within the selected timeframe.',
    )
    wo_notification_user_ids = fields.Many2many(
        'res.users',
        'res_company_wo_notification_rel',
        'company_id',
        'user_id',
        string='WO notification recipients',
        domain=[('share', '=', False)],
        help='Users that will receive email notifications about workorders producing less than the expected quantity.',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    enable_wo_notifications = fields.Boolean(
        related='company_id.enable_wo_notifications',
        readonly=False,
        string='Enable WO notifications',
        help='Send email notifications when a workorder produces less than its planned quantity.',
    )
    wo_notification_timeframe = fields.Selection(
        related='company_id.wo_notification_timeframe',
        readonly=False,
        string='WO notification range',
        help='Limit notifications to workorders created within the selected timeframe.',
    )
    wo_notification_user_ids = fields.Many2many(
        related='company_id.wo_notification_user_ids',
        readonly=False,
        string='WO notification recipients',
        domain=[('share', '=', False)],
        help='Users that will receive email notifications about workorders producing less than the expected quantity.',
    )
