# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from odoo import api, fields, models

class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def _name_search(self, name, args = None, operator = 'ilike', limit = 100, name_get_uid = None):
        if self._context.get('workcenter_id'):
            workcenter_id = self.env['mrp.workcenter'].sudo().browse(int(self._context.get('workcenter_id')))
            args = [('id', 'in', workcenter_id.user_ids.ids or [])]
        elif self._context.get('workorder_id'):
            workorder_id = self.env['mrp.workorder'].sudo().browse(int(self._context.get('workorder_id')))
            args = [('id', 'in', workorder_id.workcenter_id.user_ids.ids if workorder_id.workcenter_id and workorder_id.workcenter_id.user_ids else [])]
        return super(ResUsers, self)._name_search(name = name, args = args, operator = operator, limit = limit,
                                                 name_get_uid = name_get_uid)
