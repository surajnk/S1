# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2021-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################

from odoo import api, fields, models


class HideFieldUser(models.Model):
    _inherit = 'res.users'

    @api.model
    def create(self, vals):
        """
        Ensure caches are cleared so view definitions reflect new field
        restrictions immediately after user creation.
        """
        self.clear_caches()
        return super(HideFieldUser, self).create(vals)

    def write(self, vals):
        """
        Clear caches so updated field restrictions take effect without delay.
        """
        res = super(HideFieldUser, self).write(vals)
        self.clear_caches()
        return res

    def _compute_is_admin(self):
        """
        Hide the field restriction tab for the Admin user to avoid locking
        access to required fields.
        """
        for user in self:
            user.is_admin = user.id == self.env.ref('base.user_admin').id

    hide_field_ids = fields.Many2many(
        'ir.model.fields',
        string="Fields",
        store=True,
        help='Select fields that need to be hidden for this user.'
    )
    is_admin = fields.Boolean(compute=_compute_is_admin)
