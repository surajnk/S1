#
#    Globalteckz Pvt Ltd
#    Copyright (C) 2013-Today(www.globalteckz.com).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version
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

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class ChequeManage(models.Model):
    _name = "cheque.manage"
    _description = 'Cheque Manage'
    _order = 'id desc'

    @api.model
    def default_get(self, deafult_fields):
        res = super(ChequeManage, self).default_get(deafult_fields)
        debit_account = False
        credit_account = False
        Parameters = self.env['ir.config_parameter'].sudo()
        if res.get('cheq_type') == 'outgoing':
            debit_account = Parameters.get_param(
                'gt_cheque_management.debit_inc_account')
#            credit_account = Parameters.get_param('gt_cheque_management.credit_inc_account')
        else:
            #            debit_account = Parameters.get_param('gt_cheque_management.debit_out_account')
            credit_account = Parameters.get_param(
                'gt_cheque_management.credit_out_account')
        res.update({'debit_account': int(debit_account), 'credit_account': int(credit_account), 'bank_account': int(Parameters.get_param(
            'gt_cheque_management.deposite_account')), 'journal_id': int(Parameters.get_param('gt_cheque_management.journal_id'))})
        return res

    @api.depends('cheq_attachment_ids')
    def _get_attach(self):
        Attachment = self.env['ir.attachment']
        for attachment in self:
            attachment.attachment_count = Attachment.search_count(
                [('cheque_id', '=', attachment.id)])

    @api.depends('move_line_ids')
    def _journal_item_count(self):
        for item in self:
            item.journal_item_count = len(item.move_line_ids)

    seq_no = fields.Char(string='Sequence', copy=False)
    name = fields.Char(string='Name')
    attachment_count = fields.Integer(
        string='Attachment Count', compute='_get_attach', readonly=True, copy=False)
    journal_item_count = fields.Integer(
        string='Journal Items', compute='_journal_item_count', readonly=True, copy=False)
    payer = fields.Many2one('res.partner', 'Payee')
    bank_account = fields.Many2one('account.account', string='Bank account')
    debit_account = fields.Many2one('account.account', string='Debit account')
    credit_account = fields.Many2one(
        'account.account', string='Credit account')
    debit = fields.Monetary(default=0.0, currency_field='company_currency_id')
    credit = fields.Monetary(default=0.0, currency_field='company_currency_id')
    journal_id = fields.Many2one('account.journal', string='Journal', required=True, states={
                                 'confirm': [('readonly', True)]})
    cheque_date = fields.Date(string='Cheque Date',
                              default=fields.Date.context_today)
    cashed_date = fields.Date(string='Cashed Date', copy=False)
    return_date = fields.Date(string='Returned Date', copy=False)
    cheque_receive_date = fields.Date(string='Cheque Given/Receive Date')
    cheque_no = fields.Char(string='Cheque Number', copy=False)
    amount = fields.Float(string='Amount')
    bounced = fields.Boolean(string='Bounced')
    partner_id = fields.Many2one('res.partner', 'Company')
    cheq_type = fields.Selection(
        [('incoming', 'Incoming'), ('outgoing', 'Outgoing')])
    cheq_attachment_ids = fields.One2many(
        'ir.attachment', 'cheque_id', 'Attachment Line', copy=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('register', 'Registered'),
        ('deposit', 'Deposited'),
        ('done', 'Done'),
        ('transfer', 'Transfered'),
        ('bounce', 'Bounced'),
        ('return', 'Returned'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')
    description = fields.Text('Description')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.user.company_id)
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency", readonly=True,
                                          store=True)
    move_line_ids = fields.One2many(
        'account.move.line', 'cheque_id', readonly=True, copy=False, ondelete='restrict')

    _sql_constraints = [
        ('cheque_no_company_uniq', 'unique (cheque_no,company_id)',
         'The Cheque Number of must be unique per company !')
    ]

    @api.onchange('payer')
    def onchange_payer(self):
        if self.payer.customer:
            self.bank_account = self.payer.property_account_receivable_id.id
        elif self.payer.supplier:
            self.bank_account = self.payer.property_account_payable_id

    @api.model
    def create(self, vals):
        if vals.get('cheq_type') == 'incoming':
            vals['seq_no'] = self.env['ir.sequence'].next_by_code(
                'cheque.manage.incoming') or '/'
        else:
            vals['seq_no'] = self.env['ir.sequence'].next_by_code(
                'cheque.manage.outgoing') or '/'
        return super(ChequeManage, self).create(vals)

    def action_cashed(self):
        return {
            'res_model': 'cheque.wizard',
            # 'view_type': 'form',
            'view_mode': 'form',
            'view_id': self.env.ref('gt_cheque_management.cheque_wizard_view').id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def action_transfer(self):
        return {
            'res_model': 'cheque.transfer.wizard',
            # 'view_type': 'form',
            'view_mode': 'form',
            'view_id': self.env.ref('gt_cheque_management.cheque_transfer_wizard_view').id,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    def abc(self):
        acc_pay = self.env['account.payment'].search(
            [('move_line_ids', '=', self.ids)])
        for rec in acc_pay:
            if any(inv.state != 'open' for inv in rec.invoice_ids):
                raise ValidationError(
                    _("The payment cannot be processed because the invoice is not open!"))

            # Use the right sequence to set the name
            if rec.payment_type == 'transfer':
                sequence_code = 'account.payment.transfer'
            else:
                if rec.partner_type == 'customer_rank':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.customer.invoice'
                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.customer.refund'
                if rec.partner_type == 'supplier_rank':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.supplier.refund'
                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.supplier.invoice'
            rec.name = self.env['ir.sequence'].with_context(
                ir_sequence_date=rec.payment_date).next_by_code(sequence_code)
            if not rec.name and rec.payment_type != 'transfer':
                raise UserError(
                    _("You have to define a sequence for %s in your company.") % (sequence_code,))

            # Create the journal entry
            amount = rec.amount * \
                (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
            move = rec._create_payment_entry(amount)

            # In case of a transfer, the first journal entry created debited the source liquidity account and credited
            # the transfer account. Now we debit the transfer account and credit the destination liquidity account.
            if rec.payment_type == 'transfer':
                transfer_credit_aml = move.line_ids.filtered(
                    lambda r: r.account_id == rec.company_id.transfer_account_id)
                transfer_debit_aml = rec._create_transfer_entry(amount)
                (transfer_credit_aml + transfer_debit_aml).reconcile()

            rec.write({'state': 'posted', 'move_name': move.name})

    def action_submit(self):
        Move = self.env['account.move']
        if self.cheq_type == 'outgoing':
            credit_line = {
                'account_id': self.payer.property_account_payable_id.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.debit_account.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        else:
            credit_line = {
                'account_id': self.credit_account.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.payer.property_account_receivable_id.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        move_vals = {
            'date': fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        move_id.action_post()
        return self.write({'state': 'register'})

    def action_cancel(self):
        if not self.move_line_ids:
            raise UserError(
                _("You cannot cancel a record that is not posted yet!"))
        for rec in self:
            for move in rec.move_line_ids.mapped('move_id'):
                move.button_cancel()
                move.unlink()
            return rec.write({'state': 'cancel'})

#    It will make reverse entry for the registerd entries

    def action_bounce(self):
        Move = self.env['account.move']
        if self.cheq_type == 'outgoing':
            credit_line = {
                'account_id': self.debit_account.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.payer.property_account_payable_id.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        else:
            credit_line = {
                'account_id': self.payer.property_account_receivable_id.id,
                'partner_id': self.payer.id,
                'name': self.seq_no+'-'+'Registered',
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.credit_account.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        move_vals = {
            'date': fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        move_id.action_post()
        return self.write({'state': 'bounce', 'bounced': True})

    @api.onchange('cheq_type')
    def onchange_cheq_type(self):
        domain = {}
        if self.cheq_type:
            if self.cheq_type == 'incoming':
                domain['payer'] = [('customer', '=', True)]
            else:
                domain['payer'] = [('supplier', '=', True)]
        return {'domain': domain}

    def action_draft(self):
        return self.write({'state': 'draft'})

    def action_return(self):
        if self.bounced:
            for rec in self:
                for move in rec.move_line_ids.mapped('move_id'):
                    move.button_cancel()
                    move.unlink()
                return rec.write({'state': 'return', 'return_date': fields.Date.today()})
        else:
            Move = self.env['account.move']
            if self.cheq_type == 'outgoing':
                credit_line = {
                    'account_id': self.debit_account.id,
                    'partner_id': self.payer.id,
                    'name': self.seq_no + '-' + 'Registered',
                    'debit': 0,
                    'credit': self.amount,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
                debit_line = {
                    'account_id': self.payer.property_account_payable_id.id,
                    'partner_id': self.payer.id,
                    'name': self.seq_no + '-' + 'Registered',
                    'debit': self.amount,
                    'credit': 0,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
            else:
                credit_line = {
                    'account_id': self.payer.property_account_receivable_id.id,
                    'partner_id': self.payer.id,
                    'name': self.seq_no + '-' + 'Registered',
                    'debit': 0,
                    'credit': self.amount,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
                debit_line = {
                    'account_id': self.credit_account.id,
                    'partner_id': self.payer.id,
                    'name': self.seq_no + '-' + 'Registered',
                    'debit': self.amount,
                    'credit': 0,
                    'date_maturity': self.cheque_date,
                    'cheque_id': self.id,
                }
            move_vals = {
                'date': fields.Date.today(),
                'journal_id': self.journal_id.id,
                'ref': self.seq_no,
                'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
            }
            move_id = Move.create(move_vals)
            move_id.action_post()
            return self.write({'state': 'return', 'return_date': fields.Date.today()})

    def action_deposit(self):
        Move = self.env['account.move']
        if self.cheq_type == 'outgoing':
            credit_line = {
                'account_id': self.debit_account.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.bank_account.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        else:
            credit_line = {
                'account_id': self.bank_account.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': 0,
                'credit': self.amount,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
            debit_line = {
                'account_id': self.credit_account.id,
                'partner_id': self.payer.id,
                'name': self.seq_no + '-' + 'Registered',
                'debit': self.amount,
                'credit': 0,
                'date_maturity': self.cheque_date,
                'cheque_id': self.id,
            }
        move_vals = {
            'date': fields.Date.today(),
            'journal_id': self.journal_id.id,
            'ref': self.seq_no,
            'line_ids': [(0, 0, credit_line), (0, 0, debit_line)]
        }
        move_id = Move.create(move_vals)
        move_id.action_post()
        return self.write({'state': 'deposit'})

    def unlink(self):
        if any(bool(rec.move_line_ids) for rec in self):
            raise UserError(
                _("You cannot delete a record that is already posted!"))
        return super(ChequeManage, self).unlink()

#    @api.multi
#    def action_done(self):
#        return self.write({'state': 'deposit'})

    def open_payment_matching_screen(self):
        # Open reconciliation view for customers/suppliers
        move_line_id = False
        for move_line in self.move_line_ids:
            if move_line.account_id.reconcile:
                move_line_id = move_line.id
                break
        action_context = {'company_ids': [self.company_id.id], 'partner_ids': [
            self.payer.commercial_partner_id.id]}
        if self.payer.customer:
            action_context.update({'mode': 'customer'})
        elif self.payer.supplier:
            action_context.update({'mode': 'supplier'})
        if move_line_id:
            action_context.update({'move_line_id': move_line_id})
        print ("\n\n\n")
        print ("action_context ######### ", action_context)
        print ("\n\n\n")
        return {
            'type': 'ir.actions.client',
            'tag': 'manual_reconciliation_view',
            'context': action_context,
        }

    def button_journal_entries(self):
        return {
            'name': _('Journal Items'),
            # 'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move.line',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('cheque_id', 'in', self.ids)],
        }


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    cheque_id = fields.Many2one('cheque.manage', 'Cheque Id')


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    cheque_id = fields.Many2one('cheque.manage', 'Cheque Id')
