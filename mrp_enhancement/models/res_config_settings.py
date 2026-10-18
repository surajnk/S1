# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    allowance_notifier_user_ids = fields.Many2many(
        'res.users',
        'res_company_allowance_notifier_rel',
        'company_id',
        'user_id',
        string='Allowance notifiers',
        help='Users that will receive allowance shortage notifications for manufacturing orders.',
    )
    pc_split_by_operation = fields.Boolean(
        string='Split Pick Components by Operation',
        help="When ticked, confirming an MO creates one Pick Components "
             "transfer per first operation under the BOM lines' Multiple "
             "Operations, each going to that operation's workcenter location. "
             "Otherwise a single transfer goes to the first work order's "
             "workcenter.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    allowance_notifier_user_ids = fields.Many2many(
        related='company_id.allowance_notifier_user_ids',
        string='Allowance notifiers',
        domain=[('share', '=', False)],
        readonly=False,
        help='Users that will receive allowance shortage notifications for manufacturing orders.',
    )

    pc_split_by_operation = fields.Boolean(
        related='company_id.pc_split_by_operation',
        readonly=False,
    )
