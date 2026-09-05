# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools,_
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from datetime import date
import datetime
import logging
import json

_logger = logging.getLogger(__name__)

class ResPartnerIndustry(models.Model):
    _inherit = "res.partner.industry"

    x_sales_ind_manager = fields.Many2one('res.users', string='Manager', domain = lambda self: [("groups_id", "=", self.env.ref("ef_product.group_sales_mgr").id)])


class CustomPartner(models.Model):
    _inherit = "res.partner"

    x_customer_id         = fields.Char(string="Customer ID")
    # x_jurisdiction        = fields.Char(string="Jurisdiction")
    # x_territory           = fields.Selection([('a', 'A'),('b', 'B')],'Territory',help='Territory')
    x_language            = fields.Many2one('res.lang', string='Language')
    x_manager             = fields.Many2one('res.users', string='Manager')
    x_assigned_csr        = fields.Many2one('res.users', string='Assigned CSR')
    x_fax                 = fields.Char(string="FAX")
    x_ap_contact          = fields.Char(string="A/P Contact")
    x_gst                 = fields.Char(string="GST")
    x_pst                 = fields.Char(string="PST")
    # x_group_price_cd      = fields.Char(string="Group Price CD")
    # x_customer_price_cd   = fields.Char(string="Custome Price CD")
    x_country_code        = fields.Char(related='country_id.code', string='Jurisdiction')
    x_currency_id         = fields.Many2one('res.currency', string='Currency')
    x_sales_off           = fields.Many2one('sales.offices', string='Sales Office')
    x_freight_terms       = fields.Many2one('account.incoterms', string='Freight Terms')
    x_ship_via            = fields.Many2one('ship.via', string='Ship Via')
    # x_sales_off           = fields.Char(string="Sales Off")
    x_credit_limit        = fields.Float(string="Credit Limit")
    x_delinquent_days     = fields.Char(string="Delinquent Days")
    x_outturns            = fields.Boolean(string='Outturns', default=False)
    x_dupe_po             = fields.Boolean(string='Dupe PO', default=False)
    x_email_invoice       = fields.Boolean(string='Email Invoice', default=False)
    x_mail_invoice        = fields.Boolean(string='Mail Invoice', default=False)
    x_hold_shipment       = fields.Boolean(string='Hold Shipment', default=False)
    x_plain_label         = fields.Boolean(string='Plain Label', default=False)
    x_shipper_acct        = fields.Char(string="Shipper Acct")
    x_special_pricing     = fields.Boolean(string='Special Pricing', default=False)
    x_partner_qty         = fields.Char('Quantity Breaks')
    x_partner_uom         = fields.Many2one('uom.uom', 'Unit of Measure')
    x_partner_price_per_uom   = fields.Char('Price Per UOM')
    x_partner_price_per_value = fields.Float('Price Per Value')
    x_publisher           = fields.Many2one('publisher', string='Publisher')
    x_reference           = fields.Char(string="Reference")
    x_customer_notes = fields.Html('Customer Notes', tracking=True)
    user_id = fields.Many2one('res.users', string='Salesperson',
      help='The internal user in charge of this contact.')

    x_domain_portal = fields.Char(compute="_compute_portal_approve", readonly=True, store=False,)
    x_salesrep_domain = fields.Char(compute="_compute_salesrep", readonly=True, store=False,)
    x_customer_credits = fields.Monetary(compute='_total_credits', string="Balance",)
    receive_parent_mail = fields.Boolean(string="Receive parent mail", default=False)
    partner_attachment = fields.Many2many('ir.attachment',string="Attachment")


    def _total_credits(self):
        self.x_customer_credits = 0
        if not self.ids:
            return True
        account_types = []
        receivable_type = self.env.ref('account.data_account_type_receivable').id
        payable_type = self.env.ref('account.data_account_type_payable').id
        account_types.extend([receivable_type, payable_type])
        domain = [('partner_id', '=', self.id), ('amount_residual', '!=', 0),('account_id.user_type_id', 'in', account_types)]
        domain += [('move_id.state', '=', 'posted')]
        customer_balance = sum([x.amount_residual for x in self.env['account.move.line'].search(domain)])
        self.x_customer_credits = customer_balance

    def action_view_partner_payments(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        action['domain'] = [
            ('move_type', 'in', ('out_invoice', 'out_refund')),
            ('partner_id', 'child_of', self.id),
        ]
        action['context'] = {'default_move_type':'out_invoice', 'move_type':'out_invoice', 'journal_type': 'sale', 'search_default_unpaid': 1}
        return action

    @api.depends('x_domain_portal','x_manager')
    def _compute_portal_approve(self):
        partner_list = []
        partner_list = self.env.ref('ef_product.group_sales_mgr').users.ids
        _logger.info('partners %s',partner_list)
        for rec in self:
            rec.x_domain_portal = json.dumps(
                [('id', 'in', partner_list)]
                )

    @api.depends('x_salesrep_domain','user_id')
    def _compute_salesrep(self):
        partne_list = []
        partner_mgr_list = []
        partne_list = self.env.ref('ef_product.group_sales_rep').users.ids
        partner_mgr_list = self.env.ref('ef_product.group_sales_sup_mgr').users.ids
        #_logger.info('partners %s',partner_list)
        for rec in self:
            rec.x_salesrep_domain = json.dumps(
                ['|',('id', 'in', partne_list),('id', 'in', partner_mgr_list)]
                )

    def write(self, vals):
        if vals.get('x_customer_notes'):
            self.message_post(body=(_("Customer Notes: %s changed to %s")%(self.x_customer_notes,vals.get('x_customer_notes'))))
        res = super(CustomPartner, self).write(vals)
        return res

    def copy_contacts(self):
        contact_ids = self.env['res.partner'].search([('parent_id', '=', self.id)]).ids
        _logger.info("Contacts '%s'",contact_ids)
        if contact_ids:
            for rec in contact_ids:
                result = self.env['res.partner'].browse(rec)
                result.x_customer_notes = self.x_customer_notes
        else:
             return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _("Alert"),
                    'message': _("This Contact has no Sub-contacts"),
                    'sticky': False,
                    'className': 'bg-warning'
                }
            }

    # businesstype = fields.Selection([('customer', 'Customer'),
    #                              ('supplier', 'supplier'),
    #                              ('customer/supplier', 'Customer/Supplier')],
    #                             'Type',
    #                             default='customer')
    # rating       = fields.Selection([('platinum', 'Platinum'),
    #                              ('gold', 'Gold'),
    #                              ('silver', 'Silver'),
    #                              ('bronze', 'Bronze')],
    #                             '   Rating',
    #                             default='platinum')
    # category     = fields.Selection([('domestic', 'Domestic'),
    #                              ('export', 'Export')],
    #                             'Category',
    #                             required=True,
    #                             default='domestic',
    #                             help='Category')
    # pan          = fields.Char(string="PAN")
    # gst          = fields.Char(string="GST")
    # currency_id  = fields.Many2one('res.currency', string='Currency')
    # date_of_birth = fields.Date(string='Date Of Birth', required=True)
    # partner_category_id = fields.Many2many('res.partner.category',string='Tags')
   
 