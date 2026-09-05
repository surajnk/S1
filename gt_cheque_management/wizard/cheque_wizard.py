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


from odoo import fields, models


class ChequeWizard(models.TransientModel):
    _name = "cheque.wizard"
    _description = "Cheque Wizard"

    cheque_date = fields.Date(string='Cheque Date')

    def cash_submit(self):
        cheque_inc = self.env['cheque.manage'].search([])
        cheque_inc.cheque_date = self.cheque_date
        return cheque_inc.write({'state': 'done'})


class ChequeTransferWizard(models.TransientModel):
    _name = "cheque.transfer.wizard"
    _description = "Cheque Transfer Wizard"

    transfer_date = fields.Date(string='Transfered Date')
    contact = fields.Many2one('res.partner', 'Contact')

    def transfer_submit(self):
        cheque_inc = self.env['cheque.manage'].search([])
        return cheque_inc.write({'state': 'transfer'})


class ChequeOutgoingWizard(models.TransientModel):
    _name = "cheque.outgoing.wizard"
    _description = "Cheque Outgoing Wizard"

    cheque_date = fields.Date(string='Cheque Date')
    bank_acc = fields.Many2one('account.account', 'Bank Account')

    def cash_out_submit(self):
        cheque_id = self.env[self._context.get('active_model')].browse(
            self._context.get('active_ids'))
        Move = self.env['account.move']
        if cheque_id.cheq_type == 'outgoing':
            credit_line = {
                'account_id': cheque_id.debit_account.id,
                'partner_id': cheque_id.payer.id,
                'name': cheque_id.seq_no + '-' + 'Registered',
                'debit': 0,
                'credit': cheque_id.amount,
                'date_maturity': cheque_id.cheque_date,
                'cheque_id': cheque_id.id,
            }
            debit_line = {
                'account_id': self.bank_acc.id,
                'partner_id': cheque_id.payer.id,
                'name': cheque_id.seq_no + '-' + 'Registered',
                'debit': cheque_id.amount,
                'credit': 0,
                'date_maturity': cheque_id.cheque_date,
                'cheque_id': cheque_id.id,
            }
        else:
            credit_line = {
                'account_id': self.bank_acc.id,
                'partner_id': cheque_id.payer.id,
                'name': cheque_id.seq_no+'-'+'Registered',
                'debit': 0,
                'credit': cheque_id.amount,
                'date_maturity': cheque_id.cheque_date,
                'cheque_id': cheque_id.id,
            }
            debit_line = {
                'account_id': cheque_id.credit_account.id,
                'partner_id': cheque_id.payer.id,
                'name': cheque_id.seq_no+'-'+'Registered',
                'debit': cheque_id.amount,
                'credit': 0,
                'date_maturity': cheque_id.cheque_date,
                'cheque_id': cheque_id.id,
            }
        move_vals = {
            'date': fields.Date.today(),
            'journal_id': cheque_id.journal_id.id,
            'ref': cheque_id.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        move_id.action_post()
        cheque_id.write({'cashed_date': self.cheque_date, 'state': 'done'})
        return True
