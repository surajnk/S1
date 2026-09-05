# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle 
#
##############################################################################
from datetime import  datetime,date
from odoo import models,fields, api, _
from odoo.exceptions import ValidationError

#========For Excel=======
from io import BytesIO
import xlwt
from xlwt import easyxf
import base64
# =======================

#=======Group By=========
import itertools
from operator import itemgetter
import operator
#========================



class dev_partner_overdue_detail(models.TransientModel):
    _name ='dev.partner.overdue.detail'

    @api.model
    def get_company_id(self):
        return self.env.user.company_id.id
        
    part_type = [('customer','Receivable Accounts'),
                 ('supplier','Payable Accounts')]
    
    
    @api.model
    def _get_current_date(self):
        return date.today()
    
    start_date = fields.Date('Start Date', required="1", default=_get_current_date)
    company_id = fields.Many2one('res.company','Company',default=get_company_id, required="1")
    partner_type = fields.Selection(part_type,string="Partner's",default='customer')
    target_move = fields.Selection([('posted','All Posted Entries'),
                                    ('all','All Entries')],
                                    string='Target Moves',default='posted')
    
    ageing_by = fields.Selection([('date','Date'),('due_date','Due Date')], string='Overdue By', default='due_date', required="1")
    report_type = fields.Selection([('simple','Simple'),('break_down','Break Down')], string='Report Type', required="1", default='simple')
    excel_file = fields.Binary('Excel File')
    
    partner = fields.Selection([('all','All'),('selected','Selected')], string='Partner', default='all')
    partner_ids = fields.Many2many('res.partner', string='Partner')
              

    def print_report(self):
        if self.partner == 'selected':
            if not self.partner_ids:
                raise ValidationError(_("Please Select Partners"))
        if self.report_type == 'simple':
            return self.env.ref('dev_partner_overdue_report.action_print_dev_partner_overdue').report_action(self, data=None)
        else:
            return self.env.ref('dev_partner_overdue_report.action_print_dev_partner_overdue_break').report_action(self, data=None)
            
    
    
    def _get_move_lines(self):
        moveline_obj = self.env['account.move.line']
        domain = [('date','<=',self.start_date),('company_id','=',self.company_id.id)]
        if self.partner == 'selected':
            partner_ids = self.partner_ids.ids
            domain.append(('partner_id', 'in', partner_ids))
        
        if self.partner_type:
            if self.partner_type == 'customer':
                domain.append(('account_id.user_type_id.type', '=', 'receivable'))
            elif self.partner_type == 'supplier':
                domain.append(('account_id.user_type_id.type', '=', 'payable'))
            else:
                domain.append(('account_id.user_type_id.type', 'in', ('receivable','payable')))
                
        if self.target_move == 'posted':
            domain.append(('move_id.state', '<>', 'draft'))
        
        movelines = moveline_obj.search(domain)
        return movelines
    
    def _set_ageing(self,line):
        not_due = 0.0
        f_pe = 0.0 # 0 -30
        s_pe = 0.0 # 31-60
        t_pe = 0.0 # 61-90
        fo_pe = 0.0 # 91 ++
        if self.ageing_by == 'due_date':
            ag_date = line.date_maturity
        else:
            ag_date = line.date
            
        if ag_date and self.start_date:
            due_date=ag_date
            over_date=self.start_date
            if over_date != due_date:
                if not ag_date > self.start_date: 
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
                
    def get_partner_name(self,partner_id):
        return self.env['res.partner'].browse(partner_id).name
        
    def get_lines(self):
        move_lines = self._get_move_lines()
        lst=[]
        for move in move_lines:
            aging = self._set_ageing(move)
            lst.append({
                'partner_id':move.partner_id and move.partner_id.id or False,
                'not_due':aging.get('not_due'),
                '0_30':aging.get('0-30'),
                '31_60':aging.get('31-60'),
                '61_90':aging.get('61-90'),
                '91_120':aging.get('91-120'),
                'total':aging.get('not_due') + aging.get('0-30') + aging.get('31-60') + aging.get('61-90') + aging.get('91-120'),
            })
         
        new_lst=sorted(lst,key=itemgetter('partner_id'))
        groups = itertools.groupby(new_lst, key=operator.itemgetter('partner_id'))
        result = [{'partner_id':k,'values':[x for x in v]} for k, v in groups]
        f_result=[]
        for res in result:
            dic={
                'name':self.get_partner_name(res.get('partner_id')),
                'not_due':0.0,
                '0_30':0.0,
                '31_60':0.0,
                '61_90':0.0,
                '91_120':0.0,
                'total':0.0
            }
            for r in res.get('values'):
                dic.update({
                    'not_due': dic.get('not_due') + r.get('not_due'),
                    '0_30': dic.get('0_30') + r.get('0_30'),
                    '31_60': dic.get('31_60') + r.get('31_60'),
                    '61_90': dic.get('61_90') + r.get('61_90'),
                    '91_120': dic.get('91_120') + r.get('91_120'),
                    'total':dic.get('total')+ r.get('total'),
                })
            f_result.append(dic)
            
        f_new_list = sorted(f_result, key = lambda i: i['total'], reverse=True)
        return f_new_list
        
    def get_break_lines(self):
        move_lines = self._get_move_lines()
        lst=[]
        for move in move_lines:
            aging = self._set_ageing(move)
            date = date_due= ''
            if move.date:
                date = move.date.strftime('%d-%m-%Y')
            if move.move_id and move.move_id.invoice_date_due:
                date_due = move.move_id and move.move_id.invoice_date_due.strftime('%d-%m-%Y')
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
        
    def get_style(self):
        main_header_style = easyxf('font:height 300;'
                                   'align: horiz center;font: color black; font:bold True;'
                                   "borders: top thin,left thin,right thin,bottom thin")
                                   
        header_style = easyxf('font:height 200;pattern: pattern solid, fore_color gray25;'
                              'align: horiz center;font: color black; font:bold True;'
                              "borders: top thin,left thin,right thin,bottom thin")
        
        left_header_style = easyxf('font:height 200;pattern: pattern solid, fore_color gray25;'
                              'align: horiz left;font: color black; font:bold True;'
                              "borders: top thin,left thin,right thin,bottom thin")
        
        
        text_left = easyxf('font:height 200; align: horiz left;')
        
        text_right = easyxf('font:height 200; align: horiz right;', num_format_str='0.00')
        
        text_left_bold = easyxf('font:height 200; align: horiz left;font:bold True;')
        
        text_right_bold = easyxf('font:height 200; align: horiz right;font:bold True;', num_format_str='0.00') 
        text_center = easyxf('font:height 200; align: horiz center;'
                             "borders: top thin,left thin,right thin,bottom thin")  
        
        return [main_header_style, left_header_style,header_style, text_left, text_right, text_left_bold, text_right_bold, text_center]
        
    def get_table_label(self):
        label = ['Customer', 'O/S Amt', '< 30 DAYS', '< 60 DAYS', '< 90 DAYS', 'Older', 'Total']
        if self.report_type != 'simple':
            label = ['Date', 'Reference', 'Due Date', 'Inv Amt', 'Paid Amt', 'Remaining Amt', 'O/S Amt', '< 30 DAYS', '< 60 DAYS','< 90 DAYS', 'Older']
        
        return label
    
    def create_table_header(self,worksheet,header_style,row):
        col=0
        row =row + 2
        if self.report_type == 'simple':
            i=0
            for val in self.get_table_label():
                if i == 0:
                    worksheet.write_merge(row,row, col, col+1, val, header_style)
                    i+=1
                    col+=2
                else:
                    worksheet.write(row,col, val, header_style)
                    col+=1
        else:
            for val in self.get_table_label():
                 worksheet.write(row,col, val, header_style)
                 col+=1
        row+=1
        return worksheet, row
        
        
    def create_break_table_values(self,worksheet,header_style,text_left,text_right,text_left_bold,text_right_bold,row):
        vals = self.get_break_lines()
        col=0
        finv_amt = fpaid_amt = fremaining_amount = ff = fs = ft = ffo =ffi = 0
        for val in vals:
            partner_name = self.get_partner_name(val.get('partner_id'))
            worksheet.write_merge(row,row, col, col+10, partner_name, text_left_bold)
            row+=1
            col=0
            inv_amt = paid_amt = remaining_amount = f = s = t = fo =fi = 0
            for v in val.get('values'):
                paid_amount = v.get('inv_amount') - v.get('remaining_amount')
                
                inv_amt += v.get('inv_amount')
                paid_amt += paid_amount
                remaining_amount += v.get('remaining_amount')
                f += v.get('not_due')
                s += v.get('0_30')
                t += v.get('31_60')
                fo += v.get('61_90')
                fi += v.get('91_120')
                worksheet.write(row,col, v.get('date'), text_left)
                worksheet.write(row,col+1, v.get('invoice_number'), text_left)
                worksheet.write(row,col+2, v.get('date_due'), text_left)
                worksheet.write(row,col+3, v.get('inv_amount'), text_right)
                worksheet.write(row,col+4, paid_amount, text_right)
                worksheet.write(row,col+5, v.get('remaining_amount'), text_right)
                worksheet.write(row,col+6, v.get('not_due'), text_right)
                worksheet.write(row,col+7, v.get('0_30'), text_right)
                worksheet.write(row,col+8, v.get('31_60'), text_right)
                worksheet.write(row,col+9, v.get('61_90'), text_right)
                worksheet.write(row,col+10, v.get('91_120'), text_right)
                row+=1
                
            finv_amt += inv_amt
            fpaid_amt += paid_amt
            fremaining_amount += remaining_amount
            ff += f
            fs += s
            ft += t
            ffo += fo
            ffi += fi
            worksheet.write_merge(row,row, col,col+2, 'SUB-TOTAL', text_right_bold)
            worksheet.write(row,col+3, inv_amt, text_right_bold)
            worksheet.write(row,col+4, paid_amt, text_right_bold)
            worksheet.write(row,col+5, remaining_amount, text_right_bold)
            worksheet.write(row,col+6, f, text_right_bold)
            worksheet.write(row,col+7, s, text_right_bold)
            worksheet.write(row,col+8, t, text_right_bold)
            worksheet.write(row,col+9, fo, text_right_bold)
            worksheet.write(row,col+10, fi, text_right_bold)
            row+=1
        worksheet.write_merge(row,row, col,col+2, 'GRAND-TOTAL', text_right_bold)
        worksheet.write(row,col+3, finv_amt, text_right_bold)
        worksheet.write(row,col+4, fpaid_amt, text_right_bold)
        worksheet.write(row,col+5, fremaining_amount, text_right_bold)
        worksheet.write(row,col+6, ff, text_right_bold)
        worksheet.write(row,col+7, fs, text_right_bold)
        worksheet.write(row,col+8, ft, text_right_bold)
        worksheet.write(row,col+9, ffo, text_right_bold)
        worksheet.write(row,col+10, ffi, text_right_bold)
        row+=1
        return worksheet, row
                 
    def create_simple_table_values(self,worksheet,header_style,text_left,text_right,text_left_bold,text_right_bold,row):
        col=0
        vals = self.get_lines()
        not_due = f = s = t = fo = f_total = 0
        for val in vals:
            worksheet.write_merge(row,row, col, col+1, val.get('name'), text_left)
            not_due += val.get('not_due')
            worksheet.write(row,col+2, val.get('not_due'), text_right)
            f += val.get('0_30')
            worksheet.write(row,col+3, val.get('0_30'), text_right)
            s += val.get('31_60')
            worksheet.write(row,col+4, val.get('31_60'), text_right)
            t += val.get('61_90')
            worksheet.write(row,col+5, val.get('61_90'), text_right)
            fo += val.get('91_120')
            worksheet.write(row,col+6, val.get('91_120'), text_right)
            f_total += val.get('total')
            worksheet.write(row,col+7, val.get('total'), text_right)
            row+=1
        worksheet.write_merge(row,row, col, col+1, 'TOTAL', text_right_bold)
        worksheet.write(row,col+2, not_due, text_right_bold)
        worksheet.write(row,col+3, f, text_right_bold)
        worksheet.write(row,col+4, s, text_right_bold)
        worksheet.write(row,col+5, t, text_right_bold)
        worksheet.write(row,col+6, fo, text_right_bold)
        worksheet.write(row,col+7, f_total, text_right_bold)
        row+=1
        return worksheet, row
        
        
        
    def create_excel_header(self,worksheet,main_header_style,header_style,text_center,row):
        report_name = 'Partner Overdue Report'
        if self.report_type != 'simple':
            report_name = 'Partner Overdue Break Down Report'
        worksheet.write_merge(0, 1, 1, 5, report_name, main_header_style)
        row = row
        col=1
            
        worksheet.write(row,col, 'Company', header_style)
        worksheet.write(row,col+1, 'Date', header_style)
        worksheet.write(row,col+2, 'Overdue By', header_style)
        worksheet.write(row,col+3, 'Accounts', header_style)
        worksheet.write(row,col+4, 'Analysis Type', header_style)
        row += 1
        date = datetime.strftime(self.start_date, "%d-%m-%Y")
        
        ageing = ''
        if self.ageing_by == 'date':
            ageing = 'Date'
        else:
            ageing = 'Due Date'
        account = ''
        if self.partner_type == 'customer':
            account = 'Receivable'
        else:
            account = 'Payable'
            
        analysis=''
        if self.target_move:
            analysis = 'Posted'
        else:
            analysis = 'All'
            
        worksheet.write(row,col, self.company_id.name, text_center)
        worksheet.write(row,col+1, date, text_center)
        worksheet.write(row,col+2, ageing, text_center)
        worksheet.write(row,col+3, account, text_center)
        worksheet.write(row,col+4, analysis, text_center)
        row += 1
        return worksheet, row

    def print_excel(self):
        if self.partner == 'selected':
            if not self.partner_ids:
                raise ValidationError(_("Please Select Partners"))
    
        excel_style = self.get_style()
        main_header_style = excel_style[0]
        left_header_style = excel_style[1]
        header_style = excel_style[2]
        text_left = excel_style[3]
        text_right = excel_style[4]
        text_left_bold = excel_style[5]
        text_right_bold = excel_style[6]
        text_center = excel_style[7]
        
        
        # Define Wookbook and add sheet 
        workbook = xlwt.Workbook()
        filename = 'Partner Overdue Report.xls'
        worksheet = workbook.add_sheet('Partner Overdue')
        
        
        # Set the Width of Excel Column
        if self.report_type == 'simple':
            worksheet.col(0).width = 250 * 30
            for i in range(1,10):
                worksheet.col(i).width = 120 * 30
        else:
            for i in range(0,11):
                if i in [1,5]:
                    worksheet.col(i).width = 150 * 30
                else:
                    worksheet.col(i).width = 120 * 30
                    
        # Print Excel Header
        worksheet,row = self.create_excel_header(worksheet,main_header_style,header_style,text_center,3)
        worksheet,row = self.create_table_header(worksheet,header_style,row)
        if self.report_type == 'simple':
            worksheet,row = self.create_simple_table_values(worksheet,header_style,text_left,text_right,text_left_bold,text_right_bold,row)
        else:
             worksheet,row = self.create_break_table_values(worksheet,header_style,text_left,text_right,text_left_bold,text_right_bold,row)
        
        fp = BytesIO()
        workbook.save(fp)
        fp.seek(0)
        excel_file = base64.encodestring(fp.read())
        fp.close()
        self.write({'excel_file': excel_file})

        if self.excel_file:
            active_id = self.ids[0]
            return {
                'type': 'ir.actions.act_url',
                'url': 'web/content/?model=dev.partner.overdue.detail&download=true&field=excel_file&id=%s&filename=%s' % (
                    active_id, filename),
                'target': 'new',
            }
        
    
        
    
   

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
