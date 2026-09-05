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
#
##############################################################################
from odoo import api, fields, models


class ChequeReportWizard(models.TransientModel):
    _name = 'cheque.report.wizard'
    _description = "Cheque Report Wizard"

    date_from = fields.Date(string='Start Date')
    date_to = fields.Date(string='End Date', default=fields.Date.context_today)
    cheq_type = fields.Selection(
        [('incoming', 'Incoming'), ('outgoing', 'Outgoing')], string="Report Type", default='incoming')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('register', 'Registered'),
        ('bounce', 'Bounced'),
        ('return', 'Returned'),
        ('deposit', 'Deposited'),
        ('transfer', 'Transfered'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status')

    def print_report(self):
        return self.env.ref('gt_cheque_management.action_cheque_manage_report_document').report_action(self)

    def print_data(self):
        cheque_data = []
        if self.cheq_type == 'outgoing':
            if self.date_from and self.state:
                cheque_data = self.env['cheque.manage'].search([('cheq_type', '=', 'outgoing'), (
                    'cheque_date', '>=', self.date_from), ('cheque_date', '<=', self.date_to), ('state', '=', self.state)])
            elif self.date_from:
                cheque_data = self.env['cheque.manage'].search([('cheq_type', '=', 'outgoing'), (
                    'cheque_date', '>=', self.date_from), ('cheque_date', '<=', self.date_to)])
            elif self.state:
                cheque_data = self.env['cheque.manage'].search(
                    [('cheq_type', '=', 'outgoing'), ('cheque_date', '<=', self.date_to), ('state', '=', self.state)])
            else:
                cheque_data = self.env['cheque.manage'].search(
                    [('cheq_type', '=', 'outgoing'), ('cheque_date', '>=', self.date_to)])
        else:
            if self.date_from and self.state:
                cheque_data = self.env['cheque.manage'].search([('cheq_type', '=', 'incoming'), (
                    'cheque_date', '>=', self.date_from), ('cheque_date', '<=', self.date_to), ('state', '=', self.state)])
            elif self.date_from:
                cheque_data = self.env['cheque.manage'].search([('cheq_type', '=', 'incoming'), (
                    'cheque_date', '>=', self.date_from), ('cheque_date', '<=', self.date_to)])
            elif self.state:
                cheque_data = self.env['cheque.manage'].search(
                    [('cheq_type', '=', 'incoming'), ('cheque_date', '<=', self.date_to), ('state', '=', self.state)])
            else:
                cheque_data = self.env['cheque.manage'].search(
                    [('cheq_type', '=', 'incoming'), ('cheque_date', '<=', self.date_to)])
        return cheque_data
