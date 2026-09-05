# -*- coding: utf-8 -*-
##############################################################################
#
#    Globalteckz Pvt Ltd
#    Copyright (C) 2013-Today(www.globalteckz.com).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
##############################################################################

from odoo import fields, models ,api, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    debit_inc_account = fields.Many2one('account.account', string='Debit account',config_parameter='gt_cheque_management.debit_inc_account')
#    credit_inc_account = fields.Many2one('account.account', string='Credit account',config_parameter='gt_cheque_management.credit_inc_account')
#    debit_out_account = fields.Many2one('account.account', string='Debit account',config_parameter='gt_cheque_management.debit_out_account')
    credit_out_account = fields.Many2one('account.account', string='Credit account',config_parameter='gt_cheque_management.credit_out_account')
    deposite_account = fields.Many2one('account.account', string='Deposite account',config_parameter='gt_cheque_management.deposite_account')
    journal_id = fields.Many2one('account.journal', string='Specific Journal',config_parameter='gt_cheque_management.journal_id')


class ResPartner(models.Model):
    _inherit = "res.partner"

    customer = fields.Boolean(string='Is a Customer')
    supplier = fields.Boolean(string='Is a Vendor')
    
    
