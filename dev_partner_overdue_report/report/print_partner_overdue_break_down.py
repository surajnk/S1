# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################
from odoo import api, models
import itertools
from operator import itemgetter
import operator

class print_partner_overdue_break_down(models.AbstractModel):
    _name = 'report.dev_partner_overdue_report.dev_print_overdue_break'

    def get_partners(self,obj):
        if obj.partner_type:
            if obj.partner_type == 'customer':
                return 'Receivable Accounts'
            elif obj.partner_type == 'supplier':
                return 'Payable Accounts'
            else:
                return 'Receivable and Payable Accounts'
        
        
    def get_target_moves(self,obj):
        if obj.target_move == 'all':
            return 'All Entries'
        else:
            return 'All Posted Entries'
        
    def _get_move_lines(self, obj):
        moveline_obj = self.env['account.move.line']
        domain = [('date','<=',obj.start_date),('company_id','=',obj.company_id.id)]
        if obj.partner == 'selected':
            partner_ids = obj.partner_ids.ids
            domain.append(('partner_id', 'in', partner_ids))

        if obj.partner_type:
            if obj.partner_type == 'customer':
                domain.append(('account_id.user_type_id.type', '=', 'receivable'))
            elif obj.partner_type == 'supplier':
                domain.append(('account_id.user_type_id.type', '=', 'payable'))
            else:
                domain.append(('account_id.user_type_id.type', 'in', ('receivable','payable')))
                
        if obj.target_move == 'posted':
            domain.append(('move_id.state', '<>', 'draft'))
        
        movelines = moveline_obj.search(domain)
        return movelines
    
    def _set_ageing(self,obj, line):
        not_due = 0.0
        f_pe = 0.0 # 0 -30
        s_pe = 0.0 # 31-60
        t_pe = 0.0 # 61-90
        fo_pe = 0.0 # 91 ++
        
        if obj.ageing_by == 'due_date':
            ag_date = line.date_maturity
        else:
            ag_date = line.date
        if ag_date and obj.start_date:
            due_date=ag_date
            over_date=obj.start_date
            if over_date != due_date:
                if not ag_date > obj.start_date: 
                    days=over_date - due_date
                    days=int(str(days).split(' ')[0])
                else:
                    days= -1
            else:
                days = 0
                
            debit = line.debit - line.credit
            m_d_amt=0
            m_c_amt=0
            for m in line.matched_debit_ids:
                if m.max_date <= over_date:
                    m_d_amt += m.amount
                    
                    
            for m in line.matched_credit_ids:
                if m.max_date <= over_date:
                    m_c_amt += m.amount
                    
            p_amt= m_d_amt - m_c_amt  
            debit = debit + p_amt 
            
            if days < 0:
                not_due = debit
            elif days < 31:
                f_pe = debit 
            elif days < 61:
                s_pe = debit
            elif days < 91:
                t_pe = debit
            else:
                fo_pe = debit
    
        return {
                'not_due':not_due,
                '0-30': f_pe,
                '31-60': s_pe,
                '61-90': t_pe,
                '91-120': fo_pe,
            }
                
    
    def get_lines(self,obj):
        move_lines = self._get_move_lines(obj)
        lst=[]
        for move in move_lines:
            aging = self._set_ageing(obj,move)
            date = ''
            date_due=''
            if move.date:
                date = move.date.strftime('%d-%m-%Y')
            if move.move_id and move.move_id.invoice_date_due:
                date_due = move.move_id.invoice_date_due.strftime('%d-%m-%Y')
            lst.append({
                'partner_id':move.partner_id and move.partner_id.id or False,
                'partner_name':move.partner_id and move.partner_id.name or False,
                'invoice_number':move.move_id and move.move_id.name or False,
                'term':move.move_id and move.move_id.invoice_payment_term_id and move.move_id.invoice_payment_term_id.name or False,
                'date':date or False,
                'date_due':date_due or False,
                'not_due':aging.get('not_due'),
                '0_30':aging.get('0-30'),
                '31_60':aging.get('31-60'),
                '61_90':aging.get('61-90'),
                '91_120':aging.get('91-120'),
                'inv_amount':move.move_id and move.move_id.amount_total or 0.0,
                'remaining_amount':move.move_id and move.move_id.amount_residual or 0.0,
            })
         
        new_lst=sorted(lst,key=itemgetter('partner_id'))
        groups = itertools.groupby(new_lst, key=operator.itemgetter('partner_id'))
        result = [{'partner_id':k,'values':[x for x in v]} for k, v in groups]
        return result
        

    def get_partner_name(self,partner_id):
        return self.env['res.partner'].browse(partner_id).name
        
    def get_label(self):
        return ['< 30 Days', '< 60 Days', '< 90 Days']
        
        
    def get_formate_datetime(self,date):
        if date:
            return date.strftime('%d %b %Y %H:%M:%S')
        return ''
        
    def get_formate_date(self,date):
        if date:
            return date.strftime('%d-%m-%Y')
        return ''
        
    @api.model
    def _get_report_values(self, docids, data=None):
        doc = self.env['dev.partner.overdue.detail'].browse(docids) 
        
        return  {
            'doc_ids': docids,
            'doc_model': 'dev.partner.overdue.detail',
            'docs': doc,
            'get_lines':self.get_lines,
            'get_partners':self.get_partners,
            'get_target_moves':self.get_target_moves,
            'get_partner_name':self.get_partner_name,
            'get_label':self.get_label,
            'get_formate_datetime':self.get_formate_datetime,
            'get_formate_date':self.get_formate_date,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
