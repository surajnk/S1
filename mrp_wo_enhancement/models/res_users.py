# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, SUPERUSER_ID


class ResUsers(models.Model):
    _inherit = 'res.users'
    _description = 'Res Users'

    workcenter_ids = fields.Many2many("mrp.workcenter", 'users_mrp_workcenter_rel', 'u_id', 'wc_id', string="Work Centers")
