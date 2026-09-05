from odoo import api, fields, models, _
from odoo.tools import float_round
from odoo.exceptions import UserError
import math
import logging
import json
from odoo.exceptions import ValidationError, RedirectWarning, UserError
import datetime
from datetime import date
from datetime import datetime
import base64
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_picking(self):
        self.ensure_one()
        res = super(SaleOrder, self)._prepare_picking()
        if not res:
            return res

        # ``res`` already contains the standard picking values.  When the
        # "Ship Via" has been selected on the sale order we make sure the same
        # value is propagated to the picking that will be created from those
        # values.  ``ship_via_id`` is a regular Many2one so it expects the id of
        # the selected record (or ``False`` when it must be cleared).
        res['ship_via_id'] = self.x_sale_ship_via.id or False
        return res


    def _create_invoices(self, grouped=False, final=False):
        invoices = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)
        for order in self:
            order_invoices = invoices.filtered(lambda inv: order in inv.invoice_line_ids.sale_line_ids.order_id)
            for invoice in order_invoices:
                _logger.info(f"Processing Invoice ID: {invoice.id} for Sale Order: {order.name}")

                line_commands = []
                for sale_order_line in order.order_line:
                    labor_items = sale_order_line.x_order_line_labor_items_grid_new.filtered(lambda l: l.x_product_labor_select)
                    if not labor_items:
                        continue

                    # Find the invoice line that was actually generated FROM this order line.
                    # We do NOT modify this line at all — its price_unit/price_subtotal must
                    # keep showing customer_unit_price (material + labor blended), exactly as
                    # the client wants on the Invoice Lines tab.
                    material_line = invoice.line_ids.filtered(lambda l: sale_order_line in l.sale_line_ids)
                    if not material_line:
                        _logger.warning(f"No invoice line found for order line {sale_order_line.id}, skipping labor reallocation")
                        continue
                    material_line = material_line[:1]

                    line_labor_total = 0.0
                    labor_line_commands = []
                    for labor_item in labor_items:
                        amount = float_round(labor_item.x_labor_monetary_amount, precision_digits=2)
                        if not amount:
                            continue
                        revenue_account = labor_item.x_product_product_labor.x_labor_account.id
                        if not revenue_account:
                            _logger.error(f"Missing Revenue Account for Labor Item: {labor_item.x_product_product_labor.name}")
                            continue
                        labor_line_commands.append((0, 0, {
                            'name': labor_item.x_product_product_labor.name,
                            'quantity': 1,
                            'price_unit': amount,
                            'account_id': revenue_account,
                            'partner_id': invoice.partner_id.id,
                            'debit': 0.0,
                            'credit': amount,
                            'exclude_from_invoice_tab': True
                        }))
                        line_labor_total += amount

                    if line_labor_total:
                        # Don't touch material_line itself (keeps Invoice Lines display fully
                        # intact — full customer_unit_price, full subtotal). Instead, post a
                        # plain reversal on the SAME account: this nets that account's ledger
                        # balance down by the labor amount, while the visible invoice line is
                        # untouched. Combined with the labor credit line(s) below in the SAME
                        # write, the move stays balanced (receivable is never touched, since
                        # it was already correct).
                        _logger.info(f"Reallocating {line_labor_total} labor out of material account {material_line.account_id.display_name} (via reversal, invoice line left untouched)")
                        line_commands.append((0, 0, {
                            'name': f"Labor Reallocation - {material_line.name or sale_order_line.name}",
                            'account_id': material_line.account_id.id,
                            'partner_id': invoice.partner_id.id,
                            'debit': line_labor_total,
                            'credit': 0.0,
                            'exclude_from_invoice_tab': True
                        }))
                        line_commands.extend(labor_line_commands)

                if line_commands:
                    try:
                        invoice.write({'line_ids': line_commands})
                        _logger.info(f"Labor reallocation applied successfully for Invoice {invoice.id}")
                    except Exception as e:
                        _logger.error(f"Error reallocating labor for invoice {invoice.id}: {e}")

        return invoices
    # def _create_invoices(self, grouped=False, final=False):
    #     invoices = super(SaleOrder, self)._create_invoices(grouped=grouped, final=final)
    #     for order in self:
    #         for invoice in invoices:
    #             _logger.info(f"Processing Invoice ID: {invoice.id} for Sale Order: {order.name}")
    #             journal_entries = self.env['account.move.line'].search([('move_id', '=', invoice.id)])
    #             receivable_line = journal_entries.filtered(lambda l: l.account_id.internal_type == 'receivable')

    #             total_labor_cost = 0.0  # Track labor cost to ensure balance
    #             # Log existing journal entries BEFORE adding labor items
    #             _logger.info("Journal Entries BEFORE Adding Labor Items:")
    #             for line in invoice.line_ids:
    #                 _logger.info(f"Account: {line.account_id.name}, Debit: {line.debit}, Credit: {line.credit}")

    #             # Add labor items if applicable
    #             for sale_order_line in order.order_line:
    #                 if sale_order_line.x_order_line_labor_items_grid_new:
    #                     for labor_item in sale_order_line.x_order_line_labor_items_grid_new.filtered(lambda l: l.x_product_labor_select):
    #                         amount = float_round(labor_item.x_labor_monetary_amount, precision_digits=2)
    #                         revenue_account = labor_item.x_product_product_labor.x_labor_account.id
    #                         if not revenue_account:
    #                             _logger.error(f"Missing Revenue Account for Labor Item: {labor_item.x_product_product_labor.name}")
    #                             continue
    #                         credit_line_vals = {
    #                             'move_id': invoice.id,
    #                             'name': labor_item.x_product_product_labor.name,
    #                             'quantity': 1,
    #                             'price_unit': amount,
    #                             'account_id': revenue_account,
    #                             'partner_id': invoice.partner_id.id,
    #                             'debit': 0.0,
    #                             'credit': amount,
    #                             'exclude_from_invoice_tab': True
    #                         }
    #                         _logger.info(f"Creating Credit Entry: {credit_line_vals}")
    #                         total_labor_cost += amount
    #                         try:
    #                             labor_line = self.env['account.move.line'].create(credit_line_vals)
    #                             _logger.info(f"Labor Item Created Successfully: {labor_line.id}")
    #                         except Exception as e:
    #                             _logger.error(f"Error creating labor item: {e}")

    #             if total_labor_cost > 0:
    #                 if receivable_line:
    #                     _logger.info(f"Updating Existing Receivable Entry with Additional {total_labor_cost}")
    #                     receivable_line.write({'debit': receivable_line.debit + total_labor_cost})
    #                 else:
    #                     receivable_vals = {
    #                         'move_id': invoice.id,
    #                         'name': 'Labor Charges',
    #                         'account_id': invoice.journal_id.default_account_id.id,  # Use journal's default account
    #                         'partner_id': invoice.partner_id.id,
    #                         'debit': total_labor_cost,
    #                         'credit': 0.0,
    #                         'exclude_from_invoice_tab': True
    #                     }
    #                     _logger.info(f"Creating Debit Entry for Receivable: {receivable_vals}")
    #                     self.env['account.move.line'].create(receivable_vals)

    #     return invoices

    
    # @api.model
    # def _prepare_down_payment_section_line(self, **optional_values):
    #     down_payments_section_line = super(SaleOrder, self)._prepare_down_payment_section_line(**optional_values)
    #     down_payments_section_line.update({
    #         'x_customer_order_width': 0.0,  # Provide a default value
    #     })
    #     return down_payments_section_line

    @api.model
    def _default_custom_warehouse_id(self):
        current_branch_id = self.env.user.branch_id.id if self.env.user.branch_id else None
        # _logger.info("BRANCHCCCCCC'%s'",current_branch_id.name)
        if not current_branch_id:
            current_branch_id = self.env.context.get('branch_id')
        if current_branch_id:
            warehouse = self.env['stock.warehouse'].search([('branch_id', '=', current_branch_id)], limit=1)
            _logger.info("WAREHOUSSSSSEEE'%s'",warehouse.name)
            return warehouse.id if warehouse else False
        return False

    # @api.model
    # def default_get(self, fields):
    #     res = super(SaleOrder, self).default_get(fields)
    #     warehouse_id = self._default_warehouse_id()

    #     res.update({
    #         'warehouse_id': warehouse_id
    #     })

    def _get_invoice_address_domain(self):
        if self.remove_address_domain:
            return []
        return "[('parent_id', '=', partner_id), ('type', 'in', ['invoice'])]"

    def _get_shipping_address_domain(self):
        if self.remove_address_domain:
            return []
        return "[('parent_id', '=', partner_id), ('type', 'in', ['delivery'])]"

    x_is_sample = fields.Boolean('Sample Sale')
    x_sale_ship_via = fields.Many2one('ship.via',string='Ship Via')
    x_sale_freight_terms = fields.Many2one('freight.terms',string='Freight Terms')
    x_sale_incoterms = fields.Many2one('account.incoterms',string='Freight Incoterms')
    x_amount_labor = fields.Monetary(string='Labor Total', store=True, readonly=True, compute='_amount_all')
    x_sale_customer_notes = fields.Html('Notes')
    x_sale_customer_message = fields.One2many('sale.order.message','x_special_message','Special Messages')
    x_sale_order_amount = fields.Float('Sale Order Amount',store=True)
    x_sale_order_block_amount = fields.Float('Partner Sale Credit',store=True)
    x_delinquent_invoice = fields.Char('Invoice Number',store=True)
    x_ship_hold = fields.Boolean('Ship Hold')
    x_manual_hold = fields.Boolean('Manual Hold')
    x_credit_hold = fields.Boolean('Credit Hold')
    x_delinquent_hold = fields.Boolean('Delinquent Hold')
    credit_hold_date = fields.Date(string='Credit Hold Date', copy=False)
    delinquent_hold_date = fields.Date(string='Delinquent Hold Date', copy=False)
    manual_hold_date = fields.Date(string='Manual Hold Date', copy=False)
    ship_hold_date = fields.Date(string='Ship Hold Date', copy=False)
    x_is_multi_slit = fields.Boolean('Multiple Slit Sizes')
    x_order_multi_slit_size = fields.One2many('sale.multi.size','x_order_size_ref','Multi Slit Sizes')
    x_order_customer_msg = fields.Text(string='Customer Special Messages')
    x_order_custom_del_date = fields.Date(string='Requested Date')
    x_mrp_revised_ship_date =  fields.Date(string='Confirmed Date')
    #Custom State's & Inherit fields 
    partner_id = fields.Many2one(
        'res.partner', string='Customer', readonly=True,
        states={'hc': [('readonly', False)],'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        required=True, change_default=True, index=True, tracking=1,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",)
    partner_invoice_id = fields.Many2one(
        'res.partner', string='Invoice Address',
        readonly=True, required=True,
        states={'hc': [('readonly', False)],'draft': [('readonly', False)], 'sent': [('readonly', False)], 'sale': [('readonly', False)]},
        domain=lambda self: self._get_invoice_address_domain(),)
    partner_shipping_id = fields.Many2one(
        'res.partner', string='Delivery Address', readonly=True, required=True,
        states={'hc': [('readonly', False)],'draft': [('readonly', False)], 'sent': [('readonly', False)], 'sale': [('readonly', False)]},
        domain=lambda self: self._get_shipping_address_domain(),)

    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', check_company=True,  # Unrequired company
        required=True, readonly=True, states={'hc': [('readonly', False)],'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", tracking=1,
        help="If you change the pricelist, only newly added lines will be affected.")

    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse',
        required=True, readonly=True, states={'draft': [('readonly', False)], 'hc': [('readonly', False)],  'sent': [('readonly', False)]},
        default = lambda self: self._default_custom_warehouse_id(), check_company=True)

    state = fields.Selection([
        ('send_for_approval', 'Send for Approval'),
        ('approve', 'Approved'),
        ('hc', 'Hold Check'),
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('ch', 'Credit Hold'),
        ('dh', 'Delinquent Hold'),
        ('mh', 'Manual Hold'),
        ('sh', 'Ship Hold'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),
        ('complained', 'Complained')
        ], string='Status', readonly=True, copy=False, index=True, tracking=True, default='draft')

    remove_address_domain = fields.Boolean(string="Show All Addresses", default=False)
    approved = fields.Boolean(string='Approved', default=False, copy=False)
    skip_approval = fields.Boolean(string='Skip Approval', default=False, copy=False,tracking=True)

    # @api.onchange('client_order_ref')
    # def _onchange_check_duplicate_client_order_ref(self):
    #     if self.client_order_ref:
    #         duplicate_orders = self.search([
    #             ('client_order_ref', '=', self.client_order_ref),
    #             ('id', 'not in', self.ids if self.ids else [-1]),
    #             ('state', 'not in', ['cancel'])
    #         ])
    #         if duplicate_orders:
    #             return {
    #                 'warning': {
    #                     'title': _("Duplicate Client Order Reference"),
    #                     'message': _('The Client Order Reference is already used in another sale order: %s.') % (duplicate_orders.mapped('name')),
    #                 }
    #             }
    @api.constrains('client_order_ref')
    def _check_duplicate_client_order_ref(self):
        for order in self:
            if order.client_order_ref:
                duplicate_orders = self.search([
                    ('client_order_ref', '=', order.client_order_ref),
                    ('partner_id', '=', order.partner_id.id),
                    ('id', '!=', order.id),
                    ('state', 'not in', ['cancel'])
                ])
                if duplicate_orders:
                    raise ValidationError(
                        _('The Client Order Reference is already used in another sale order: %s.') %
                        ', '.join(duplicate_orders.mapped('name'))
                    )

    @api.onchange('partner_id', 'remove_address_domain')
    def _onchange_partner_id(self):
        if self.remove_address_domain:
            return {
                'domain': {
                    'partner_invoice_id': [],
                    'partner_shipping_id': [],
                }
            }
        elif self.partner_id:
            partner = self.partner_id.parent_id or self.partner_id
            self.partner_invoice_id = False
            self.partner_shipping_id = False
            return {
                'domain': {
                    'partner_invoice_id': [('parent_id', '=', partner.id), ('type', 'in', ['invoice'])],
                    'partner_shipping_id': [('parent_id', '=', partner.id), ('type', 'in', ['delivery'])],
                }
            }
        else:
            return {
                'domain': {
                    'partner_invoice_id': [],
                    'partner_shipping_id': [],
                }
            }


    def action_draft(self):
        orders = self.filtered(lambda s: s.state in ['cancel', 'sent','ch','dh','mh','sh'])
        return orders.write({
            'state': 'draft',
            'signature': False,
            'signed_by': False,
            'signed_on': False,
            'x_sale_order_amount': 0,
            'x_sale_order_block_amount': 0,
            'x_delinquent_invoice': False,
            'x_ship_hold':False,
            'x_manual_hold':False,
            'x_credit_hold':False,
            'x_delinquent_hold':False
        })

    def unlink(self):
        for order in self:
            if order.state not in ('draft', 'cancel','hc'):
                raise UserError(_('You can not delete a sent quotation or a confirmed sales order. You must first cancel it.'))
        return super(SaleOrder, self).unlink()

    def action_ship_hold(self):
        if self.filtered(lambda so: so.state == 'draft,ch,dh,mh'):
            raise UserError(_('Only records in Draft/from other type of Holds can be put into Ship Hold.'))
        # for order in self:
        #     order.message_subscribe(partner_ids=order.partner_id.ids)
        for rec in self:
            template_res = self.env['ir.model.data'].xmlid_to_res_id('ef_sales.email_template_sale_ship_hold',raise_if_not_found=False)
            #_logger.info("TEMPLATE_RES'%s'",template_res)
            template_final = self.env['mail.template'].browse(template_res)
            if template_final:
                template_final.sudo().send_mail(self.id, force_send=True)
        self.write({'state': 'sh',
                    'x_ship_hold':True,
                    'x_manual_hold':False,
                    'x_sale_order_amount': 0,
                    'x_sale_order_block_amount': 0,
                    'x_delinquent_invoice': False,
                    'ship_hold_date':fields.Date.today()
        })

    def action_manual_hold(self):
        if self.filtered(lambda so: so.state == 'draft,ch,dh,sh'):
            raise UserError(_('Only records in Draft/from other type of Holds can be put into Manual Hold.'))
        # for order in self:
        #     order.message_subscribe(partner_ids=order.partner_id.ids)
        for rec in self:
            template_res = self.env['ir.model.data'].xmlid_to_res_id('ef_sales.email_template_sale_manual_hold',raise_if_not_found=False)
            #_logger.info("TEMPLATE_RES'%s'",template_res)
            template_final = self.env['mail.template'].browse(template_res)
            if template_final:
                _logger.info("TEMPLATE_FINAL'%s'",template_final)
                template_final.sudo().send_mail(rec.id, force_send=True)
        self.write({'state': 'mh',
                    'x_ship_hold':False,
                    'x_manual_hold':True,
                    'x_sale_order_amount': 0,
                    'x_sale_order_block_amount': 0,
                    'x_delinquent_invoice': False,
                    'manual_hold_date':fields.Date.today()
        })

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for rec in self.order_line:
            rec.write({'x_mrp_line_ship_date': self.x_order_custom_del_date})

        for order in self:
            ship_via = order.x_sale_ship_via.id or False
            if ship_via or any(picking.ship_via_id for picking in order.picking_ids):
                order.picking_ids.write({'ship_via_id': ship_via})

        if self.x_ship_hold == True:
            template_res = self.env['ir.model.data'].xmlid_to_res_id('ef_sales.email_template_sale_ship_hold_release',raise_if_not_found=False)
            _logger.info("ACTION CONFIRM STATE'%s'",self._origin.state)
            template_final = self.env['mail.template'].browse(template_res)
            if template_final:
                _logger.info("TEMPLATE_FINAL'%s'",template_final)
                template_final.sudo().send_mail(self.id, force_send=True)
            self.write({
                    'x_ship_hold':False,
            })
        if self.x_manual_hold == True:
            template_res = self.env['ir.model.data'].xmlid_to_res_id('ef_sales.email_template_sale_manual_hold_release',raise_if_not_found=False)
            template_final = self.env['mail.template'].browse(template_res)
            if template_final:
                template_final.sudo().send_mail(self.id, force_send=True)
            self.write({
                    'x_manual_hold':False,
            })
        if self.x_credit_hold == True:
            template_res = self.env['ir.model.data'].xmlid_to_res_id('ef_sales.email_template_sale_credit_hold_release',raise_if_not_found=False)
            template_final = self.env['mail.template'].browse(template_res)
            if template_final:
                template_final.sudo().send_mail(self.id, force_send=True)
            self.write({
                    'x_credit_hold':False,
            })
        if self.x_delinquent_hold == True:
            template_res = self.env['ir.model.data'].xmlid_to_res_id('ef_sales.email_template_sale_deli_hold_release',raise_if_not_found=False)
            template_final = self.env['mail.template'].browse(template_res)
            if template_final:
                template_final.sudo().send_mail(self.id, force_send=True)
            self.write({
                    'x_delinquent_hold':False,
            })
        return res

    def action_hold(self):
        sale_amount = 0
        check_amount = 0
        sale_hist_amount = 0 
        difference_days = 0
        h_flag=0
        diff_invoice_number = ''
        #res = super(SaleOrder, self).action_confirm()
        if not self.x_order_custom_del_date or not self.client_order_ref:
            raise ValidationError(_("Both 'Requested Date' and 'Client Order Reference' must be set before proceeding."))

        sale_orders_hist = self.env['sale.order'].search([('partner_id', '=', self.partner_id.id),'|',('state', '=', 'done'),('state', '=', 'sale')])
        invoices = self.env['account.move'].search([('move_type','=', 'out_invoice'),('state','=','posted'),('payment_state','=','not_paid'),('partner_id','=',self.partner_id.id)],order='id asc',limit=1)
        for reci in invoices:
            difference_days = (date.today() - reci.invoice_date).days
            diff_invoice_number = reci.name
            _logger.info("Invoice Difference Days'%s'",difference_days)
        for reco in sale_orders_hist:
            sale_amount += reco.amount_total
            sale_hist_amount =  sale_amount
            check_amount = sale_amount + self.amount_total
            _logger.info("SO Number'%s'",reco.name)
            _logger.info("Sale Amount'%s'",sale_amount)
            # _logger.info("SO Amount'%s'",reco.amount_total)
        #self.x_sale_order_amount = sale_amount

        if (check_amount > float(self.partner_id.x_credit_limit) and (self.partner_id.x_credit_limit>0.00)):
            _logger.info("Sale Amount'%s'",sale_amount)
            self.x_sale_order_amount = check_amount
            self.x_sale_order_block_amount = self.partner_id.x_credit_limit
            template_res = self.env['ir.model.data'].xmlid_to_res_id('ef_sales.email_template_sale_credit_hold',raise_if_not_found=False)
            #_logger.info("TEMPLATE_RES'%s'",template_res)
            template_final = self.env['mail.template'].browse(template_res)
            if template_final:
                template_final.sudo().send_mail(self.id, force_send=True)
            self.write({'state': 'ch','x_credit_hold':True,'credit_hold_date':fields.Date.today()})
            h_flag=1
            sale_amount = 0
            check_amount = 0
            sale_hist_amount = 0
        elif int(self.partner_id.x_delinquent_days) > 0:
            _logger.info("Within Delinquent")
            if difference_days > int(self.partner_id.x_delinquent_days):
                _logger.info("Within Delinquent")
                self.x_delinquent_invoice = diff_invoice_number
                template_res = self.env['ir.model.data'].xmlid_to_res_id('ef_sales.email_template_sale_deli_hold',raise_if_not_found=False)
                #_logger.info("TEMPLATE_RES'%s'",template_res)
                template_final = self.env['mail.template'].browse(template_res)
                if template_final:
                    template_final.sudo().send_mail(self.id, force_send=True)
                self.write({'state': 'dh','x_delinquent_hold':True,'delinquent_hold_date':fields.Date.today()})
                h_flag=1
                diff_invoice_number = 0
                difference_days = 0
        
        if h_flag==0:
                self.write({'state': 'draft'})


    @api.onchange('partner_id')
    def onchange_partner_id(self):
        #self = self.with_company(self.company_id)
        _logger.info("SELFFF VAALUE'%s'",self)
        if self.partner_id.company_type == 'company':
            self.x_sale_ship_via = self.partner_id.x_ship_via.id
            self.incoterm = self.partner_id.x_freight_terms.id
        elif self.partner_id.company_type == 'person':
            _logger.info("INDIVIDUALLLL")
            self.x_sale_ship_via = self.partner_id.parent_id.x_ship_via.id
            self.incoterm = self.partner_id.parent_id.x_freight_terms.id
        res = super(SaleOrder, self).onchange_partner_id()
        return res

    @api.onchange('partner_id')
    def onchange_partner_id_notes(self):
        for rec in self:
            if not rec.partner_id:
                # clear fields if no partner
                rec.x_sale_customer_notes = False
                rec.x_sale_customer_message = [(5, 0, 0)]
                return

            partner = rec.partner_id
            parent = partner.parent_id

            # Notes: prefer child’s notes; fall back to parent’s notes (if any)
            notes = partner.x_customer_notes or (parent and parent.x_customer_notes) or False
            rec.x_sale_customer_notes = notes

            # Domain: child and optional parent in a single IN
            partner_ids = [partner.id] + ([parent.id] if parent else [])
            domain = [('customer_id', 'in', partner_ids)]
            _logger.debug("customer special message domain: %s", domain)

            cust_msgs = self.env['customer.special.message'].search(domain)
            _logger.debug("customer special message found: %s", cust_msgs)

            # Build x_sale_customer_message lines (clear then append)
            lines_cmd = [(5, 0, 0)]
            if cust_msgs:
                # if message_line is o2m on customer.special.message
                for msg in cust_msgs:
                    for qc in msg.message_line:
                        lines_cmd.append((0, 0, {'x_sale_special_message': qc.name}))
            rec.x_sale_customer_message = lines_cmd

            # Compose warning once, avoid multiple returns
            warn_msg = None
            has_notes = bool(notes and notes != "<p><br></p>")
            has_spec = bool(cust_msgs)

            if has_notes and has_spec:
                warn_msg = _("This Customer has Customer Notes and Special Messages")
            elif has_notes:
                warn_msg = _("This Customer has Customer Notes")
            elif has_spec:
                warn_msg = _("This Customer has Special Message")

            if warn_msg:
                return {
                    'warning': {
                        'title': _("Alert"),
                        'message': warn_msg,
                    }
                }

    # @api.onchange('partner_id')
    # def onchange_partner_id_notes(self):
    #     notification={}
    #     for rec in self:
    #         domain = [('customer_id', '=', rec.partner_id.id)]
    #         if rec.partner_id.parent_id:
    #             print('domainnnnnnnnnn')
    #             domain = ['|', ('customer_id', '=', rec.partner_id.id),
    #                       ('customer_id', '=', rec.partner_id.parent_id.id)]
    #             print('dom',domain)

    #         cust_msg = self.env['customer.special.message'].search(domain)
    #         print('cust_msg',cust_msg)
    #         if rec.partner_id.x_customer_notes:
    #             rec.x_sale_customer_notes = rec.partner_id.x_customer_notes
    #         elif rec.partner_id.parent_id.x_customer_notes:
    #             rec.x_sale_customer_notes = rec.partner_id.parent_id.x_customer_notes
    #         if cust_msg and rec.partner_id:
    #             val1={}
    #             rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #             res=[(5,0,0)]
    #             for qc in cust_msg.message_line:
    #                 val = {
    #                 'x_sale_special_message': qc.name,
    #                 }
    #                 res.append((0,0,val))
    #             rec.x_sale_customer_message = res
    #         if rec.partner_id and rec.partner_id.x_customer_notes != "<p><br></p>" and cust_msg:
    #             _logger.info('Cust alert if 1')
    #             return {
    #                 'warning': {
    #                     'title': _("Alert"),
    #                     'message': _("This Customer has Customer Notes and Special Messages"),
    #                 }
    #             } 
    #         if rec.partner_id and rec.partner_id.x_customer_notes != "<p><br></p>":
    #             return {
    #                 'warning': {
    #                     'title': _("Alert"),
    #                     'message': _("This Customer has Customer Notes"),
    #                 }
    #             }             
    #         if cust_msg and rec.partner_id and rec.partner_id.x_customer_notes == "<p><br></p>":
    #             _logger.info('Cust alert if 3')
    #             return {
    #                 'warning': {
    #                     'title': _("Alert"),
    #                     'message': _("This Customer has Special Message"),
    #                 }
    #             }

    def construct_message_html(self, res_order_line):
        message_html = "<ul>"
        for _, _, val in res_order_line:
            if isinstance(val, dict):  # Check if val is a dictionary
                message_html += f"<li>{val.get('x_sale_special_message', '')}</li>"
        message_html += "</ul>"
        return message_html

    def show_popup(self):
        # Your logic to prepare data for the popup
        popup_data = {
            'title': 'Your Popup Title',
            'message': 'Your Popup Message',
        }

        # Return an action to display the popup
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_title': popup_data['title'], 'default_message': popup_data['message']},
        }

    # @api.onchange('partner_id', 'order_line', 'order_line.x_order_line_labor_items_grid_new.x_product_labor_select')
    # def onchange_partner_id_messages(self):
    #     for order in self:
    #         customer_messages = self._get_customer_messages(order.partner_id)
    #         order.x_order_customer_msg = "\n".join(customer_messages)

    #         order_lines_messages = []
    #         for order_line in order.order_line:
    #             order_line_messages = self._get_order_line_messages(order_line)
    #             order_line.x_sale_line_customer_message = "\n".join(order_line_messages)
    #             order_lines_messages.extend(order_line_messages)

    #         order.x_sale_customer_message = "\n".join(order_lines_messages)

    # def _get_customer_messages(self, partner):
    #     messages = []
    #     if partner:
    #         customer_msg = self.env['customer.special.message'].search([('customer_id', '=', partner.id)])
    #         for msg in customer_msg:
    #             if msg.message_type == 'all':
    #                 messages.extend(msg.message_line.mapped('name'))
    #     return messages

    # def _get_order_line_messages(self, order_line):
    #     messages = []
    #     uom_name = order_line.x_order_customer_uom.name
    #     if uom_name in ('yds', 'shts'):
    #         messages.extend(self._get_special_messages(order_line.product_id, uom_name))
    #     return messages

    # def _get_special_messages(self, product, uom_name):
    #     messages = []
    #     cust_msg = self.env['customer.special.message'].search([('customer_id', '=', product.partner_id.id), ('order_type', 'in', [uom_name, 'both'])])
    #     for msg in cust_msg:
    #         for line in msg.message_line:
    #             if msg.message_type == 'commodity_class':
    #                 messages.append(f"{product.name} - {line.customer_special_message_id.product_commodity_code_id.name} - {line.name}")
    #             elif msg.message_type == 'product':
    #                 messages.append(f"{product.name} - {line.name}")
    #             elif msg.message_type == 'item_group':
    #                 messages.append(f"{product.name} - {line.customer_special_message_id.product_item_group_id.name} - {line.name}")
    #             elif msg.message_type == 'embossing':
    #                 messages.append(f"{product.name} - {line.embossing_id.name} - {line.name}")
    #             elif msg.message_type == 'labor_item':
    #                 labor_items = order_line.x_order_line_labor_items_grid_new.filtered(lambda labor: labor.x_product_labor_select and labor.x_product_product_labor.id == line.labor_items_id.id)
    #                 for labor_item in labor_items:
    #                     messages.append(f"{product.name} - {line.customer_special_message_id.labor_items_id.name} - {line.name}")
    #     return messages


    # @api.onchange('partner_id','order_line','order_line.x_order_line_labor_items_grid_new.x_product_labor_select')
    # def onchange_partner_id_messages(self):
    #     res=[(5,0,0)]
    #     res_order_line=[(5,0,0)]
    #     res_order_line1=[(5,0,0)]
    #     val={}
    #     listToStr = ''
    #     for rec in self:
    #         cust_msg = self.env['customer.special.message'].search([('customer_id', '=', rec.partner_id.id)])
    #         for recx in cust_msg:
    #             if recx.message_type == 'all':
    #                         val1={}
    #                         for qc in recx.message_line:
    #                             listToStr += qc.name + " " + "\n"
    #         rec.x_order_customer_msg = listToStr
    #         if rec.partner_id:
    #             cust_msg_yds_uom = self.env['customer.special.message'].search(['|',('order_type', '=', 'yards'), ('order_type', '=', 'both'),('customer_id', '=', rec.partner_id.id)])
    #             cust_msg_shts_uom = self.env['customer.special.message'].search(['|',('order_type', '=', 'sheets'), ('order_type', '=', 'both'), ('customer_id', '=', rec.partner_id.id)])
    #         else:
    #             cust_msg_yds_uom = self.env['customer.special.message'].search(['|',('order_type', '=', 'yards'), ('order_type', '=', 'both')])
    #             cust_msg_shts_uom = self.env['customer.special.message'].search(['|',('order_type', '=', 'sheets'), ('order_type', '=', 'both')])
    #         #logger.info("Cust UOM Test '%s'", cust_msg_uom)
    #         for recs in self.order_line:
    #             if recs.x_order_customer_uom.name == 'yds':
    #                 res_order_line=[(5,0,0)]
    #                 for rex in cust_msg_yds_uom:
    #                     if rex.message_type == 'commodity_class' and rex.product_commodity_code_id.id == recs.product_id.x_class_commodity_group.id:
    #                         val1={}
    #                         rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                         _logger.info("MSSSGGGGGGG GEHHHEE")
    #                         for qc in rex.message_line:
    #                             val = {
    #                             'x_sale_special_message':  recs.product_id.name + " - " + qc.customer_special_message_id.product_commodity_code_id.name + " - " + qc.name,
    #                             }
    #                             res.append((0,0,val))
    #                         res_order_line.append((0,0,val))
    #                         if res_order_line:
    #                             recs.write({'x_show_popup': True})
    #                     if rex.message_type == 'product' and rex.product_id.id == recs.product_id.id:
    #                         val1={}
    #                         val2={}
    #                         rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                         #_logger.info("MSSSGGGGGGG GEHHHEE")
    #                         for qc in rex.message_line:
    #                             val2 = {
    #                             'x_sale_special_message':  recs.product_id.name + " - " + qc.name,
    #                             }
    #                             res.append((0,0,val2))
    #                             res_order_line.append((0,0,val2))
    #                     if rex.message_type == 'item_group' and rex.product_item_group_id.id == recs.product_id.x_product_item.id:
    #                         val1={}
    #                         val3={}
    #                         rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                         #_logger.info("MSSSGGGGGGG GEHHHEE")
    #                         for qc in rex.message_line:
    #                             val3 = {
    #                             'x_sale_special_message':  recs.product_id.name + " - " + qc.customer_special_message_id.product_item_group_id.name + " - " + qc.name,
    #                             }
    #                             res.append((0,0,val3))
    #                             res_order_line.append((0,0,val3))
    #                     if rex.message_type == 'embossing' and rex.embossing_id.id == recs.product_id.x_product_embossing.id:
    #                         val1={}
    #                         val4={}
    #                         rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                         #_logger.info("MSSSGGGGGGG GEHHHEE")
    #                         for qc in rex.message_line:
    #                             val4 = {
    #                             'x_sale_special_message':  recs.product_id.name + " - " + qc.embossing_id.name + " - " + qc.name,
    #                             }
    #                             res.append((0,0,val4))
    #                             res_order_line.append((0,0,val4))
    #                     if rex.message_type == 'labor_item':
    #                         for labor_recs in recs.x_order_line_labor_items_grid_new:
    #                             if labor_recs.x_product_labor_select == True and rex.labor_items_id.id == labor_recs.x_product_product_labor.id:
    #                                 val1={}
    #                                 val4={}
    #                                 rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                                 #_logger.info("MSSSGGGGGGG GEHHHEE")
    #                                 for qc in rex.message_line:
    #                                     val4 = {
    #                                     'x_sale_special_message':  recs.product_id.name + " - " + qc.customer_special_message_id.labor_items_id.name + " - " + qc.name,
    #                                     }
    #                                     res.append((0,0,val4))
    #                                     res_order_line.append((0,0,val4))                                
    #                         _logger.info("RES VALUESSSSS '%s'",res_order_line)
    #                 recs.x_sale_line_customer_message = res_order_line
    #             if recs.x_order_customer_uom.name == 'shts':
    #                 res_order_line=[(5,0,0)]
    #                 for rex in cust_msg_shts_uom:
    #                     if rex.message_type == 'commodity_class' and rex.product_commodity_code_id.id == recs.product_id.x_class_commodity_group.id:
    #                         val1={}
    #                         rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                         #_logger.info("MSSSGGGGGGG GEHHHEE")
    #                         for qc in rex.message_line:
    #                             val = {
    #                             'x_sale_special_message':  recs.product_id.name + " - " + qc.customer_special_message_id.product_commodity_code_id.name + " - " + qc.name,
    #                             }
    #                             res.append((0,0,val))
    #                             res_order_line.append((0,0,val))
    #                     if rex.message_type == 'product' and rex.product_id.id == recs.product_id.id:
    #                         val1={}
    #                         val2={}
    #                         rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                         #_logger.info("MSSSGGGGGGG GEHHHEE")
    #                         for qc in rex.message_line:
    #                             val2 = {
    #                             'x_sale_special_message':  recs.product_id.name + " - " + qc.name,
    #                             }
    #                             res.append((0,0,val2))
    #                             res_order_line.append((0,0,val2))
    #                     if rex.message_type == 'item_group' and rex.product_item_group_id.id == recs.product_id.x_product_item.id:
    #                         val1={}
    #                         val3={}
    #                         rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                         #_logger.info("MSSSGGGGGGG GEHHHEE")
    #                         for qc in rex.message_line:
    #                             val3 = {
    #                             'x_sale_special_message':  recs.product_id.name + " - " + qc.customer_special_message_id.product_item_group_id.name + " - " + qc.name,
    #                             }
    #                             res.append((0,0,val3))
    #                             res_order_line.append((0,0,val3))
    #                     if rex.message_type == 'embossing' and rex.embossing_id.id == recs.product_id.x_product_embossing.id:
    #                         val1={}
    #                         val4={}
    #                         rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                         #_logger.info("MSSSGGGGGGG GEHHHEE")
    #                         for qc in rex.message_line:
    #                             val4 = {
    #                             'x_sale_special_message':  recs.product_id.name + " - " + qc.embossing_id.name + " - " + qc.name,
    #                             }
    #                             res.append((0,0,val4))
    #                             res_order_line.append((0,0,val4))
    #                     if rex.message_type == 'labor_item':
    #                         for labor_recs in recs.x_order_line_labor_items_grid_new:
    #                             if labor_recs.x_product_labor_select == True and rex.labor_items_id.id == labor_recs.x_product_product_labor.id:
    #                                 val1={}
    #                                 val4={}
    #                                 rec.write({'x_sale_customer_message': [(5, 0, val1)]})
    #                                 #_logger.info("MSSSGGGGGGG GEHHHEE")
    #                                 for qc in rex.message_line:
    #                                     val4 = {
    #                                     'x_sale_special_message':  recs.product_id.name + " - " + qc.customer_special_message_id.labor_items_id.name + " - " + qc.name,
    #                                     }
    #                                     res.append((0,0,val4))
    #                                     res_order_line.append((0,0,val4))                                
    #                         _logger.info("RES VALUESSSSS '%s'",res_order_line)
    #                 recs.x_sale_line_customer_message = res_order_line
    #         rec.x_sale_customer_message = res
            
    @api.onchange('order_line.x_show_popup')
    def onchange_sample(self):
        #_logger.info("HEREE0011'%s'",self.x_show_popup)
        for rec in self.order_line:
            if rec.x_show_popup:
                    return {
                        'warning': {
                            'title': _("Alert"),
                            'message': _("This Customer has Special Message1111"),
                        }
                    }

    @api.model
    def calculate_customer_messages(self, partner_id, order_line, labor_items):
        # Perform your calculations here based on the provided parameters
        # Fetch customer messages based on partner_id, order_line, labor_items, etc.
        # This is just a placeholder, replace it with your actual logic
        customer_messages = "Your calculated customer messages"

        # Return the updated data including x_sale_line_customer_message
        return {'x_sale_line_customer_message': customer_messages}


    @api.onchange('x_is_sample')
    def onchange_sample(self):
        for rec in self:
            if rec.x_is_sample:
                pricelist_val = self.env['product.pricelist'].search([('name', '=', 'Sample Pricelist')])
                self.pricelist_id = pricelist_val.id
            else:
                self.pricelist_id = ''
    
    @api.depends('order_line.price_total','order_line.x_order_line_labor_items_grid_new','order_line.x_order_line_labor_items_grid_new.x_labor_monetary_amount')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = amount_tax = amount_labor = 0.0
            for line in order.order_line:
                if line.x_labor_amount_monetary:
                    amount_untaxed += line.price_subtotal
                    amount_tax += line.price_tax
                    amount_labor += line.x_labor_amount_monetary
                else:
                    amount_untaxed += line.price_subtotal
                    amount_tax += line.price_tax
            order.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'x_amount_labor': amount_labor,
                'amount_total': amount_untaxed + amount_tax + amount_labor,
            })

    @api.onchange('x_order_custom_del_date')
    def onchange_del_date(self):
        for rec in self:
            if self.x_order_custom_del_date:
                # Use noon instead of midnight to prevent timezone shift crossing date boundary
                rec.commitment_date = self.x_order_custom_del_date.strftime('%Y-%m-%d 12:00:00')
    # @api.onchange('x_order_custom_del_date')
    # def onchange_del_date(self):
    #     for rec in self:
    #         _logger.info('HEREEEEEE')
    #         if self.x_order_custom_del_date:
    #             rec.commitment_date = self.x_order_custom_del_date.strftime('%Y-%m-%d 00:00:00')

    @api.constrains('x_sale_line_customer_message.x_sale_special_message')
    def check_conditions_before_save(self):
        _logger.info("HNENWNWNWNWN")
        for rec in self:
            if rec.x_sale_line_customer_message.x_sale_special_message:
                raise ValidationError('Your warning message here')

class SaleOrderMessage(models.Model):
    _name="sale.order.message"

    x_sale_special_message =  fields.Char('Message')
    x_special_message = fields.Many2one('sale.order')
    x_special_message_line = fields.Many2one('sale.order.line')

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # def _prepare_invoice_line(self, **optional_values):
    #     res = super(SaleOrderLine, self)._prepare_invoice_line(**optional_values)
    #     if self.is_downpayment:  # Check if the line is a downpayment
    #         res.pop('x_customer_order_width', None)  # Remove the field
    #     return res

    # @api.depends('product_id')
    # def _get_workcenters(self):
    #     #self.ensure_one() domain="[('country_id', 'in', country_ids)]"
    #     self.x_sale_line_workcenters = False
    #     machines = self.product_id.product_tmpl_id.x_product_wc.mapped(id)
    #     #_logger.warning("Machine Obj1-'%s'",machines)

    #@api.onchange('x_order_customer_uom')

    # @api.onchange('product_id')
    # def get_embossers(self):
    #     embossers_list = []
    #     res = {}
    #     if self.product_id:
    #         if self.product_id.x_product_product_emboss:
    #             for rec1 in self.product_id.x_product_product_emboss:
    #                 embossers_list.append(rec1.x_mrp_embosser.id)
    #         #_logger.info("Embossers List'%s'",embossers_list)        
    #     else:
    #         self.x_sale_line_workcenters :' '
    #     res['domain'] = {'x_sale_line_workcenters': [('id', 'in', embossers_list)]}
    #     return res


    pricing_info = fields.Char('Pricing',readonly=True,store=True)
    product_uom = fields.Many2one('uom.uom', string='Product UOM', domain="[('category_id', '=', product_uom_category_id)]")
    x_sale_line_item_group = fields.Many2one('product.item.group','Item Group')
    x_customer_order_width = fields.Float('Customer Width',digits='EF Product', required=False)
    x_customer_order_length = fields.Float('Customer Length',digits='EF Product')
    x_product_order_trim_width = fields.Float('Trim Width')
    x_product_order_trim_length = fields.Float('Trim Length')
    x_product_order_waste = fields.Float('Waste(%) Allowance')
    x_order_customer_uom = fields.Many2one('uom.uom','Customer UOM',store=True,domain=[('x_frequent', '=', True)])
    x_order_master_yards = fields.Integer('Required Master Yards',compute='_compute_master_yards',store=True)
    x_approx_material_weight = fields.Integer('Approx Material Weight', compute='_compute_approx_metal_weight', store=True)
    x_sale_material_orientation = fields.Many2one('sale.orientation',string='Material Orientation')
    #x_material_orientation = fields.Selection(selection='_product_customer_uom_change',string='Material Orientation')
    x_order_publisher = fields.Many2one('publisher','Publisher')
    x_ref1 = fields.Char('Ref #1')
    x_ref2 = fields.Char('Ref #2')
    x_order_machine_length = fields.Integer('Machine Length',default=40)
    x_order_line_labor_items_grid = fields.One2many('product.commodity.code.labor','x_sale_order_labor_item','Labor Items')
    x_order_line_labor_items_grid_new = fields.One2many('sale.product.labor','x_product_labor_order_line','Labor Items')
    x_order_line_bom = fields.One2many('sale.product.bom','x_sale_order_mst','Items')
    x_sale_line_customer_message = fields.One2many('sale.order.message','x_special_message_line','Special Messages',compute='_compute_sale_line_customer_message',store=True, copy=False)
    x_sale_line_workcenters = fields.Many2one('mrp.workcenter','Embosser')
    workcenter_domain = fields.Char(compute="_compute_portal_approve", readonly=True, store=False, )
    x_order_line_workcenters = fields.Many2many('mrp.workcenter',string='Order Line Workcenters')
    x_labor_amount_monetary = fields.Monetary(compute='_compute_labor_amount', string='Labor Amount', readonly=True, store=True)
    x_order_line_embossing = fields.Many2one('product.embossing','Embossing')
    put_up_rolls = fields.Float("Put Up(Rolls)")
    uom_put_up = fields.Float("Put up")
    total_put_ups = fields.Float("Total Put Ups", compute='_compute_total_put_ups', inverse="_inverse_total_put_ups",store=True,readonly=False,)
    additional_put_ups = fields.Float("Additional Put Ups")
    put_up_uom_name = fields.Char(related='x_order_customer_uom.name')
    outs = fields.Float("Outs")
    put_up_size = fields.Float("Put up size")
    customer_unit_price = fields.Float("Customer Unit Price",digits='EF Price',compute='_compute_customer_unit_price',readonly=False,store=True,copy=False)
    x_order_line_tol_over = fields.Char('Over %')
    x_order_line_tol_under = fields.Char('Under %')
    x_is_multi_slit_order_line = fields.Boolean('Multiple Slit Sizes')
    x_order_multi_slit_size_order_line = fields.One2many('sale.multi.size','x_order_line_size_ref','Multiple Slit Sizes')
    x_selected_item_width = fields.Float('Item Width',store=True,copy=False)
    x_sum_total_size = fields.Float("Total Size Sum",compute='_compute_total_item_size')
    x_mrp_line_ship_date = fields.Date(string='Requested Date')
    x_mrp_line_revised_ship_date = fields.Date(string='Confirmed Date')
    x_show_popup = fields.Boolean("Show Popup")
    x_order_line_comments = fields.Text(string='Order Comments')
    
    x_customer_order_width_mm = fields.Float('Customer Width (mm)', digits='EF Product')
    x_customer_order_length_mm = fields.Float('Customer Length (mm)', digits='EF Product')
    x_customer_units = fields.Boolean('Customer Units')
    x_manual_put_ups = fields.Boolean(string="Manual Put-Ups", default=False)


    def _inverse_total_put_ups(self):
        # No extra logic needed; field is stored and editable.
        return

    @api.depends('put_up_rolls', 'uom_put_up', 'additional_put_ups')
    def _compute_total_put_ups(self):
        for line in self:
            if line.x_manual_put_ups:
                # Manual mode: do NOT overwrite user's stored value
                line.total_put_ups = line.total_put_ups or 0.0
                continue
            base_put_ups = line.put_up_rolls * line.uom_put_up if line.put_up_rolls and line.uom_put_up else 0.0
            additional_put_ups = line.additional_put_ups if line.additional_put_ups > 0 else 0.0
            line.total_put_ups = base_put_ups + additional_put_ups

    @api.onchange('put_up_rolls', 'uom_put_up', 'product_uom_qty')
    def _onchange_validate_put_up_qty(self):
        for line in self:
            if line.x_manual_put_ups:
                # Manual mode: don't auto-calc anything
                return
            if line.product_uom_qty and line.uom_put_up:
                rolls = int(line.product_uom_qty // line.uom_put_up)
                remainder = line.product_uom_qty - (rolls * line.uom_put_up)

                line.put_up_rolls = rolls
                line.additional_put_ups = remainder
            elif line.put_up_rolls:
                # When rolls are provided, compute the put up value directly
                line.uom_put_up = line.product_uom_qty / line.put_up_rolls if line.put_up_rolls else 0
                line.additional_put_ups = 0

            total_qty = (line.put_up_rolls * line.uom_put_up) + line.additional_put_ups
            # if line.product_uom_qty and total_qty != line.product_uom_qty:
            #     raise UserError(
            #         _("(Put Up Rolls * Put Up) plus Additional Put Ups does not match the Product Quantity. Please adjust the values.")
            #     )

    @api.onchange('x_manual_put_ups')
    def _onchange_manual_put_ups(self):
        for line in self:
            if line.x_manual_put_ups:
                # Manual ON: keep current values as-is
                continue

            # Manual OFF: apply the same computation logic
            if line.product_uom_qty and line.uom_put_up:
                rolls = int(line.product_uom_qty // line.uom_put_up)
                remainder = line.product_uom_qty - (rolls * line.uom_put_up)

                line.put_up_rolls = rolls
                line.additional_put_ups = remainder

            elif line.put_up_rolls:
                line.uom_put_up = line.product_uom_qty / line.put_up_rolls if line.put_up_rolls else 0
                line.additional_put_ups = 0

            # Refresh total_put_ups instantly in the form view (compute-like)
            base_put_ups = line.put_up_rolls * line.uom_put_up if line.put_up_rolls and line.uom_put_up else 0.0
            additional_put_ups = line.additional_put_ups if line.additional_put_ups > 0 else 0.0
            line.total_put_ups = base_put_ups + additional_put_ups
    # @api.constrains('put_up_rolls', 'uom_put_up', 'product_uom_qty')
    # def _check_put_up_and_master_width_values(self):
    #     for line in self:
    #         if line.put_up_rolls and line.uom_put_up:
    #             calculated_qty = line.put_up_rolls * line.uom_put_up
    #             if line.product_uom_qty and calculated_qty != line.product_uom_qty:
    #                 raise ValidationError(
    #                     _("(Put Up Rolls * Put Up) does not match the Product Quantity.")
    #                 )


    @api.onchange('x_customer_order_width_mm')
    def _onchange_customer_order_width_mm(self):
        if self.x_customer_order_width_mm:
            self.x_customer_order_width = self.x_customer_order_width_mm / 25.4  # Convert mm to inches

    @api.onchange('x_customer_order_length_mm')
    def _onchange_customer_order_length_mm(self):
        if self.x_customer_order_length_mm:
            self.x_customer_order_length = self.x_customer_order_length_mm / 25.4  # Convert mm to inches


    @api.depends('x_order_customer_uom', 'product_id', 'order_id.partner_id')
    def _compute_sale_line_customer_message(self):
        for line in self:
            line.x_sale_line_customer_message = [(5, 0, 0)]
            res_order_line = []
            if line.x_order_customer_uom.name == 'yds':
                res_order_line = line._get_special_messages('yards')
            elif line.x_order_customer_uom.name == 'shts':
                res_order_line = line._get_special_messages('sheets')
            line.x_sale_line_customer_message = res_order_line
            messages = line.x_sale_line_customer_message
            line.x_show_popup = bool(messages)

    def _get_special_messages(self, uom_name):
        messages = []
        for rex in self.env['customer.special.message'].search(['|',('customer_id', '=', self.order_id.partner_id.id),('customer_id', '=', self.order_id.partner_id.parent_id.id),('order_type', 'in', [uom_name, 'both'])]):
            for line in rex.message_line:
                if rex.message_type == 'commodity_class' and rex.product_commodity_code_id.id == self.product_id.x_class_commodity_group.id:
                    messages.append((0, 0, {'x_sale_special_message': f"{self.product_id.name} - {line.customer_special_message_id.product_commodity_code_id.name} - {line.name}"}))
                elif rex.message_type == 'all':
                    messages.append((0, 0, {'x_sale_special_message': f"{line.name}"}))
                elif rex.message_type == 'product' and rex.product_id.id == self.product_id.id:
                    messages.append((0, 0, {'x_sale_special_message': f"{self.product_id.name} - {line.name}"}))
                elif rex.message_type == 'item_group' and rex.product_item_group_id.id == self.product_id.x_product_item.id:
                    messages.append((0, 0, {'x_sale_special_message': f"{self.product_id.name} - {line.customer_special_message_id.product_item_group_id.name} - {line.name}"}))
                elif rex.message_type == 'embossing' and rex.embossing_id.id == self.product_id.x_product_embossing.id:
                    messages.append((0, 0, {'x_sale_special_message': f"{self.product_id.name} - {line.embossing_id.name} - {line.name}"}))
                elif rex.message_type == 'labor_item':
                    labor_items = self.order_id.order_line.x_order_line_labor_items_grid_new.filtered(lambda labor: labor.x_product_labor_select and labor.x_product_product_labor.id == rex.labor_items_id.id)
                    for labor_item in labor_items:
                        messages.append((0, 0, {'x_sale_special_message': f"{self.product_id.name} - {line.customer_special_message_id.labor_items_id.name} - {line.name}"}))
        return messages

    def concatenate_names(self):
        names = ""
        for rec in self.x_sale_line_customer_message:
            if rec.x_sale_special_message:
                names += rec.x_sale_special_message + "\n"
        return names[:-2]

    @api.onchange('x_show_popup')
    def onchange_sample(self):
        _logger.info("HEREE0011'%s'",self.x_show_popup)
        for rec in self:
            if rec.x_show_popup:
                message = _("%s") % rec.concatenate_names()
                return {
                        'warning': {
                            'title': _("Alert"),
                            'message': message,
                        }
                    }

    def _confirmation_needed(self):
    # Implement your condition to determine if a confirmation popup is needed
    # For example, you may check certain conditions or settings here
        if self.x_show_popup:
            _logger.info("HEREE0011")
            return True
        else:
            _logger.info("HEREE0022")
            return False

    def _display_popup(self):
        # Action to display the popup
        return {
            'name': _('Sale Order Line Saved'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.ui.view',
            'view_mode': 'form',
            'view_type': 'form',
            'views': [(self.env.ref('ef_sales.view_sale_order_line_popup').id, 'form')],
            'target': 'new',
        }

    def action_close_popup(self):
        # Action to close the popup
        return {'type': 'ir.actions.act_window_close'}

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get('display_type', self.default_get(['display_type'])['display_type']):
                values.update(product_id=False, price_unit=0, product_uom_qty=0, product_uom=False, customer_lead=0)

            values.update(self._prepare_add_missing_fields(values))
        _logger.info("ATLEASTT  HEREE1111")
        lines = super().create(vals_list)
        for line in lines:
            if line.product_id and line.order_id.state == 'sale':
                msg = _("Extra line with %s ") % (line.product_id.display_name,)
                line.order_id.message_post(body=msg)
                # create an analytic account if at least an expense product
                if line.product_id.expense_policy not in [False, 'no'] and not line.order_id.analytic_account_id:
                    line.order_id._create_analytic_account()

        self._display_popup()
        return lines

    # @api.depends('x_order_multi_slit_size_order_line')
    # def _compute_total_item_size(self):
    #     for rec in self.x_order_multi_slit_size_order_line:
    #         _logger.info("SUMMMMMMMM ")
    #         rec.x_sum_total_size = sum(rec.x_total_size for rec in self.x_is_multi_slit_order_line)
    #         _logger.info("SUMMMMMMMM '%s'",rec.x_sum_total_size)

    @api.depends('x_order_multi_slit_size_order_line.x_total_size', 'x_product_order_trim_width')
    def _compute_total_item_size(self):
        for line in self:
            line.x_sum_total_size = sum(line.x_order_multi_slit_size_order_line.mapped('x_total_size')) + line.x_product_order_trim_width

    @api.onchange('x_order_multi_slit_size_order_line', 'x_order_multi_slit_size_order_line.x_total_size', 'x_product_order_trim_width')
    def _onchange_check_total_size_limit(self):
        for line in self:
            if line.x_is_multi_slit_order_line and line.x_selected_item_width and line.x_sum_total_size > line.x_selected_item_width:
                return {
                    'warning': {
                        'title': _("Size Limit Exceeded"),
                        'message': _(
                            "Total slit size including trim (%.2f) exceeds the allowed item width (%.2f)."
                        ) % (line.x_sum_total_size, line.x_selected_item_width)
                    }
                }

    @api.constrains('x_order_multi_slit_size_order_line', 'x_product_order_trim_width', 'x_selected_item_width')
    def _check_total_size_limit(self):
        for line in self:
            if line.x_is_multi_slit_order_line and line.x_selected_item_width and line.x_sum_total_size > line.x_selected_item_width:
                raise ValidationError(_(
                    "Total slit size including trim (%.2f) exceeds the allowed item width (%.2f) on line '%s'."
                ) % (line.x_sum_total_size, line.x_selected_item_width, line.product_id.display_name or line.name or ''))


    
    #         for line in self:
    #             if line.x_order_line_bom:
    #                 for rec in line.x_order_line_bom:
    #                     if rec.x_product_bom_select:
    #                         _logger.info("Units Required'%s'",rec.x_unit_req)
    #                         line.x_order_master_yards = rec.x_unit_req
    #                         break;
    #                     else:
    #                         line.x_order_master_yards = 0


    # @api.onchange('x_is_multi_slit_order_line','x_order_multi_slit_size_order_line')
    # def _check_multi_line(self):
    #     for rec in self.x_order_multi_slit_size_order_line:
    #         _logger.info("SUMMMMMMMM ")
    #         total_sum = sum(rec.x_total_size for rec in self.x_is_multi_slit_order_line)
    #         _logger.info("SUMMMMMMMM '%s'",total_sum)

    # @api.onchange("put_up_rolls", "uom_put_up", "product_uom_qty")
    # def onchange_for_quantity_validation(self):
    #     if self.put_up_rolls and self.uom_put_up:
    #         cal_qty = self.put_up_rolls * self.uom_put_up
    #         if cal_qty > self.product_uom_qty:
    #             raise ValidationError(_("Can not exceed the Product Qty."))

    # @api.constrains("put_up_rolls", "uom_put_up", "product_uom_qty")
    # def _validation_for_quantity(self):
    #     for line in self:
    #         if line.put_up_rolls and line.uom_put_up:
    #             cal_qty = line.put_up_rolls * line.uom_put_up
    #             if cal_qty > line.product_uom_qty:
    #                 raise ValidationError(_("Can not exceed the Product Qty."))

    # @api.onchange("outs", "put_up_size", "x_customer_order_width")
    # def onchange_for_master_width_validation(self):
    #     """
    #     """
    #     if self.outs and self.put_up_size:
    #         cal_master_width = self.outs * self.put_up_size
    #         if cal_master_width > self.x_customer_order_width:
    #             raise ValidationError(_("Can not exceed the Master Width."))

    # @api.constrains("outs", "put_up_size", "x_customer_order_width")
    # def _check_master_width(self):
    #     for line in self:
    #         if line.outs and line.put_up_size:
    #             cal_master_width = line.outs * line.put_up_size
    #             if cal_master_width > line.x_customer_order_width:
    #                 raise ValidationError(_("Can not exceed the Master Width."))

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id','x_order_master_yards','customer_unit_price','x_customer_units','order_id.skip_approval')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            limit = self.env['ir.config_parameter'].sudo().get_param(
                'ef_sales.so_limit')
            is_approve = self.env['ir.config_parameter'].sudo().get_param(
                'ef_sales.so_order_approval')
            if line.x_order_master_yards:
                print('line.x_order_master_yards',line.x_order_master_yards)
                if line.x_customer_units:  # Explicitly check for True
                    price = line.customer_unit_price * (1 - (line.discount or 0.0) / 100.0)
                    taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
                else:
                    price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                    taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.x_order_master_yards, product=line.product_id, partner=line.order_id.partner_shipping_id)
                line.update({
                    'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })
                if self.env.context.get('import_file', False) and not self.env.user.user_has_groups('account.group_account_manager'):
                    line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])
                if not line.order_id.skip_approval:
                    if float(limit) > 0 and is_approve:
                        if taxes['total_included'] > float(limit):
                            if line.order_id.state not in ['hc', 'ch', 'mh', 'dh', 'sh'] and not line.order_id.approved:
                                line.order_id.write({
                                    'state': 'send_for_approval',
                                })

                            pdf_content, _ = line.order_id.env.ref('ef_sales.action_report_sale_custom_order')._render_qweb_pdf(
                                line.order_id.id)
                            attachment = self.env['ir.attachment'].create({
                                'name': f'Sales Order - {line.order_id.name}.pdf',
                                'type': 'binary',
                                'datas': base64.b64encode(pdf_content),
                                'res_model': 'sale.order',
                                'res_id': line.order_id.id,
                                'mimetype': 'application/pdf'
                            })

                            # Get recipients
                            manager = line.order_id.partner_id.x_manager  # Assuming partner manager is the user_id of the partner
                            sales_rep = line.order_id.user_id
                            recipient_ids = []

                            if manager:
                                recipient_ids.append(manager.partner_id.id)
                            if sales_rep:
                                recipient_ids.append(sales_rep.partner_id.id)

                            if not recipient_ids:
                                raise UserError("No valid recipients (partner manager or sales rep) found.")


                            # Create the email
                            template = self.env['mail.mail'].create({
                                'subject': f'Sales Order Approval: {line.order_id.name}',
                                'body_html': f"""
                                                <p>Hello,</p>
                                                <br></br>
                                                <p>The sales order <strong>{line.order_id.name}</strong> need approval.</p>
                                                <p><a href="{line.order_id.get_portal_url()}">View Order in Odoo</a></p>
                                                <br></br>
                                                <p>Regards,<br/>Odoo System</p>
                                            """,
                                'email_to': ','.join(
                                    [partner.email for partner in self.env['res.partner'].browse(recipient_ids) if
                                     partner.email]),
                                'attachment_ids': [(6, 0, [attachment.id])],
                            })

                            template.send()
            else:
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_shipping_id)
                line.update({
                    'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                    'price_total': taxes['total_included'],
                    'price_subtotal': taxes['total_excluded'],
                })
                if self.env.context.get('import_file', False) and not self.env.user.user_has_groups('account.group_account_manager'):
                    line.tax_id.invalidate_cache(['invoice_repartition_line_ids'], [line.tax_id.id])
                if not line.order_id.skip_approval:
                    if float(limit) > 0 and is_approve:
                        if taxes['total_included'] > float(limit):
                            if line.order_id.state not in ['hc', 'ch', 'mh', 'dh', 'sh'] and not line.order_id.approved:
                                line.order_id.write({
                                    'state': 'send_for_approval',
                                })

                            pdf_content, _ = line.order_id.env.ref(
                                'ef_sales.action_report_sale_custom_order')._render_qweb_pdf(
                                line.order_id.id)
                            attachment = self.env['ir.attachment'].create({
                                'name': f'Sales Order - {line.order_id.name}.pdf',
                                'type': 'binary',
                                'datas': base64.b64encode(pdf_content),
                                'res_model': 'sale.order',
                                'res_id': line.order_id.id,
                                'mimetype': 'application/pdf'
                            })

                            # Get recipients
                            manager = line.order_id.partner_id.x_manager  # Assuming partner manager is the user_id of the partner
                            sales_rep = line.order_id.user_id
                            recipient_ids = []

                            if manager:
                                recipient_ids.append(manager.partner_id.id)
                            if sales_rep:
                                recipient_ids.append(sales_rep.partner_id.id)

                            if not recipient_ids:
                                raise UserError("No valid recipients (partner manager or sales rep) found.")

                            # Create the email
                            template = self.env['mail.mail'].create({
                                'subject': f'Sales Order Approval: {line.order_id.name}',
                                'body_html': f"""
                                                <p>Hello,</p>
                                                <br></br>
                                                <p>The sales order <strong>{line.order_id.name}</strong> need approval.</p>
                                                <p><a href="{line.order_id.get_portal_url()}">View Order in Odoo</a></p>
                                                <br></br>
                                                <p>Regards,<br/>Odoo System</p>
                                            """,
                                'email_to': ','.join(
                                    [partner.email for partner in self.env['res.partner'].browse(recipient_ids) if
                                     partner.email]),
                                'attachment_ids': [(6, 0, [attachment.id])],
                            })

                            template.send()




    @api.depends('workcenter_domain','product_id','x_sale_line_workcenters')
    def _compute_portal_approve(self):
        partner_list = []
        for rec in self.product_id.x_product_emboss:
            partner_list.append(rec.x_mrp_embosser.id)
        for rec in self:
            rec.workcenter_domain = json.dumps(
                [('id', 'in', partner_list)]
            )

    @api.depends('x_order_master_yards', 'x_customer_order_width', 'x_customer_order_length')
    def _compute_approx_metal_weight(self):
        for line in self:
            if line.x_customer_order_length == 0.0000:
                customer_length = 36
            else:
                customer_length = line.x_customer_order_length

            if line.x_order_master_yards > 0.000 and line.x_customer_order_width > 0.000 and customer_length > 0.000 and line.x_sale_line_item_group and line.x_sale_line_item_group.x_basis_size > 0.000 and line.x_sale_line_item_group.x_basis_weight > 0.000:
                pounds = (line.x_customer_order_width * customer_length / line.x_sale_line_item_group.x_basis_size * line.x_sale_line_item_group.x_basis_weight*0.002)
                line.x_approx_material_weight = (line.product_uom_qty * pounds)
            else:
                line.x_approx_material_weight = 0.00

    # @api.onchange('x_sale_line_item_group')
    # def onchange_x_sale_item_group(self):
    #     if self.x_sale_line_item_group == False:
    #         self.product_id = False

    @api.onchange('x_order_line_bom','x_order_line_bom.x_product_bom_select','x_product_order_trim_width')
    def item_change(self):
        for rec in self.x_order_line_bom:
            if rec.x_product_bom_select:
                self.x_selected_item_width = (rec.x_product_product_widthInt - self.x_product_order_trim_width)
            # if not rec.x_product_bom_select:
            #     self.x_selected_item_width = 0.00

            # else:
            #     self.x_selected_item_width = 0.00
            #     _logger.info("ITEEMMMM WIDTHHHH'%s'",rec.x_product_product_widthInt)


    @api.onchange('x_sale_line_item_group','x_order_line_embossing')
    def onchange_x_sale_line_item_group(self):
        if self.x_sale_line_item_group:
            if not self.product_id:
                self.product_id = False
            self.x_product_order_trim_width = self.x_sale_line_item_group.x_commodity_class.x_trim_width
            self.x_product_order_trim_length = self.x_sale_line_item_group.x_commodity_class.x_trim_length
            self.x_product_order_waste = self.x_sale_line_item_group.x_commodity_class.x_waste
            product_list = []
            # product_ids = self.env['product.product'].search([('x_product_item', '=', self.x_sale_line_item_group.id),('x_product_product_embossing','=',self.x_order_line_embossing.id)])
            if self.x_sale_line_item_group and self.x_order_line_embossing:
                #_logger.info("INSIDDEEEE ONCHANGEE ITEMMMM  IFFFF GROUPPP")
                product_ids = self.env['product.product'].search(
                    [('x_product_item', '=', self.x_sale_line_item_group.id),
                     ('x_product_product_embossing', '=', self.x_order_line_embossing.id)])
            elif self.x_sale_line_item_group and not self.x_order_line_embossing:
                #_logger.info("INSIDDEEEE ONCHANGEE ITEMM IFFFF ELSEEE GROUPPP")
                product_ids = self.env['product.product'].search(
                    [('x_product_item', '=', self.x_sale_line_item_group.id)])
            for product in product_ids:
                product_list.append(product.id)
            if self.product_id.id not in product_list:
                self.product_id = False
            return {'domain': {'product_id': [('id', 'in', product_list)]}}
        else:
            product_list = []
            product_ids = self.env['product.product'].search([])
            for product in product_ids:
                product_list.append(product.id)
            if self.product_id.id not in product_list:
                self.product_id = False
            return {'domain': {'product_id': [('id', 'in', product_list)]}}

    @api.onchange('x_order_master_yards')
    def update_units_required(self):
        tol_flag=False
        for rec in self:
            if rec.x_order_master_yards:
                labor_min_charge_my=labor_charge_my=labor_extension_my=labor_amount_my=0
                rl1_my=rl2_my=nameval_labor_my=''
                for rec1 in rec.x_order_line_labor_items_grid_new:
                    if not rec1.x_product_labor_cu:
                        rec1.x_labor_unit_req = rec.x_order_master_yards
                        labor_ids_br_load_my = self.env['labor.items'].browse(rec1.x_product_product_labor.id)
                            #rec.x_labor_unit_req = rec.x_product_labor_order_line.product_uom_qty
                        labor_min_charge_my = labor_ids_br_load_my.x_min_charge
                        rec1.x_labor_minimum = labor_ids_br_load_my.x_min_charge
                        if labor_ids_br_load_my.x_no_of_break_quantities_grid:
                            for reca in labor_ids_br_load_my.x_no_of_break_quantities_grid:
                                rl1_my=rlmy=nameval_labor_my=''
                                labor_charge=labor_extension=0
                                nameval_labor_my = reca.name.split("-")
                                if ((rec.x_order_master_yards >= int(nameval_labor_my[0])) and (rec.x_order_master_yards <= int(nameval_labor_my[1]))): 
                                    labor_charge_my = reca.x_charge
                                    rec1.x_labor_unit_value = labor_charge_my
                                    labor_extension_my = (reca.x_charge * rec.x_order_master_yards)
                                    rec1.x_labor_extension = labor_extension_my
                                    if ((reca.x_charge * rec.x_order_master_yards) < labor_min_charge_my):
                                        labor_amount_my = labor_min_charge_my
                                        rec1.x_labor_amount = labor_amount_my
                                    else:
                                        labor_amount_my = reca.x_charge * rec.x_order_master_yards
                                        rec1.x_labor_amount = labor_amount_my
                product_tolerance_id = self.env['product.product'].browse(rec.product_id.id)
                for tol in product_tolerance_id.x_tolerances_m2.x_tolerance_lines:
                    split_values_tol = tol.x_range_tolerance_yds.split('-')
                    if rec.x_order_master_yards >= float(split_values_tol[0]) and rec.x_order_master_yards <= float(split_values_tol[1]):
                        rec.x_order_line_tol_over = str(tol.x_tolerance_over)
                        rec.x_order_line_tol_under = str(tol.x_tolerance_under)
                        tol_flag=True
                if tol_flag==True:
                    break
            else:
                _logger.info("Inside Else UPDATE UNITS ")
                labor_min_charge_my=0
                rec.x_order_line_tol_over = ''
                rec.x_order_line_tol_under = ''
                for rec1 in rec.x_order_line_labor_items_grid_new:
                    if not rec1.x_product_labor_cu:
                        rec1.x_labor_unit_req = 0
                        labor_ids_br_load_my = self.env['labor.items'].browse(rec1.x_product_product_labor.id)
                        labor_min_charge_my = labor_ids_br_load_my.x_min_charge
                        rec1.x_labor_minimum = labor_ids_br_load_my.x_min_charge
                        rec1.x_labor_unit_value = 0
                        rec1.x_labor_extension = 0
                        rec1.x_labor_amount = 0 


    @api.depends('x_order_line_labor_items_grid_new','x_order_line_labor_items_grid_new.x_labor_amount')
    def _compute_labor_amount(self):
        for rec in self:
            total = 0.0
            for line in rec.x_order_line_labor_items_grid_new:
                if line.x_product_labor_select:
                    total += line.x_labor_amount# why is there a discount in a field named amount_undiscounted ??
            rec.x_labor_amount_monetary = total

    @api.depends('x_labor_amount_monetary', 'price_subtotal')
    def _compute_customer_unit_price(self):
        """
        """
        for rec in self:
            if not rec.x_customer_units:
                # print("rec==========>>>", rec.price_subtotal, " + ", rec.x_labor_amount_monetary, " = ", rec.price_subtotal + rec.x_labor_amount_monetary)
                subtotal = (rec.x_order_master_yards * rec.price_unit) + rec.x_labor_amount_monetary
                _logger.info("MASTER YDS'%s'",rec.x_order_master_yards)
                _logger.info("PRICE UNITTTT'%s'",rec.price_unit)
                _logger.info("LABORR AMOUNT'%s'",rec.x_labor_amount_monetary)
                _logger.info("Subtotal'%s'",subtotal)
                if rec.product_uom_qty:
                    rec.customer_unit_price = subtotal / rec.product_uom_qty
                    _logger.info("CST UNIT PRICE'%s'",rec.customer_unit_price)
                else:
                    rec.customer_unit_price = 0.0

    @api.depends('x_order_line_bom','x_order_line_bom.x_product_bom_select','x_order_line_bom.x_unit_req','product_uom_qty','x_customer_order_width')
    def _compute_master_yards(self):
            for line in self:
                if line.x_order_line_bom:
                    for rec in line.x_order_line_bom:
                        if rec.x_product_bom_select:
                            _logger.info("Units Required'%s'",rec.x_unit_req)
                            line.x_order_master_yards = rec.x_unit_req
                            break;
                        else:
                            line.x_order_master_yards = 0
                
    @api.onchange('x_order_customer_uom')
    def _product_customer_uom_change(self):
        #_logger.info("Customer UoM value '%s'",self.x_order_customer_uom.name)
        orientation_obj =self.env['sale.orientation'].search([('x_orientation_uom', '=', self.x_order_customer_uom.name)])
        orientation_list = []
        for data in orientation_obj:
            orientation_list.append(data.id)

        res = {}
        res['domain'] = {'x_sale_material_orientation': [('id', 'in', orientation_list)]}
        return res
       
    #Embossers list

    @api.onchange('product_id','x_order_master_yards')
    def over_under_values(self):
        for rec in self:
            if rec.product_id.x_tolerances_m2:
                for reca in rec.product_id.x_tolerances_m2.x_tolerance_lines:
                    nameval_tol = reca.x_range_tolerance_yds.split("-")
                    if ((self.x_order_master_yards >= int(nameval_tol[0])) and (self.x_order_master_yards <= int(nameval_tol[1]))): 
                        self.x_order_line_tol_over = reca.x_tolerance_over
                        self.x_order_line_tol_under = reca.x_tolerance_under



    @api.onchange('product_id','product_uom_qty','x_product_order_trim_width','x_product_order_trim_length','x_customer_order_width','x_customer_order_length','x_sale_line_item_group','x_order_customer_uom')
    def values_change(self):
        res1=[(5,0,0)]
        if not self.product_id or not self.x_sale_line_item_group:
            self.x_order_line_bom = res1
            self.x_order_line_labor_items_grid_new = res1
            self.name=''


    @api.onchange('product_id','product_uom_qty','x_product_order_trim_width','x_product_order_trim_length','x_customer_order_width','x_customer_order_length','x_sale_line_item_group','x_order_customer_uom')
    def product_id_change(self):
        if self.product_id:
            val={}
            val1={}
            res1=[(5,0,0)]
            res2=[(5,0,0)]
            labor_min_charge=labor_charge=labor_extension=labor_amount=0
            rl1=rl2=nameval_labor=''
            product_ids = []
            if self.product_id and not self.x_sale_line_item_group:
                self.x_sale_line_item_group = self.product_id.x_product_item
            self.x_order_line_embossing = self.product_id.x_product_embossing
            self.name = self.product_id.default_code
            self.put_up_rolls = 0
            self.uom_put_up = 0
            self.outs = 0
            self.put_up_size = 0
            item_grp = self.env['product.item.group'].search([('id', '=', self.x_sale_line_item_group.id)])
            product_comm = self.env['product.commodity.code'].browse(item_grp.x_commodity_class.id)
            if self.x_product_order_trim_width == 0:
                self.x_product_order_trim_width = 0
            # else:
            #     self.x_product_order_trim_width = product_comm.x_trim_width
            if self.x_product_order_trim_length == 0:
                self.x_product_order_trim_length = 0
            # else:
            #     self.x_product_order_trim_length = product_comm.x_trim_length
            if self.x_product_order_waste == 0:
                self.x_product_order_waste = 0
            # else:
            #     self.x_product_order_waste = product_comm.x_waste
            if product_comm.x_labor_items_grid:
                for rec in product_comm.x_labor_items_grid:
                    labor_min_charge=0
                    if rec.x_labor_item.x_customer_units:
                        labor_ids_br_load = self.env['labor.items'].browse(rec.x_labor_item.id)
                        #rec.x_labor_unit_req = rec.x_product_labor_order_line.product_uom_qty
                        labor_min_charge = labor_ids_br_load.x_min_charge
                        if labor_ids_br_load.x_no_of_break_quantities_grid:
                            for reca in labor_ids_br_load.x_no_of_break_quantities_grid:
                                rl1=rl2=nameval_labor=''
                                labor_charge=labor_extension=0
                                nameval_labor = reca.name.split("-")
                                if ((self.product_uom_qty >= int(nameval_labor[0])) and (self.product_uom_qty <= int(nameval_labor[1]))): 
                                    labor_charge = reca.x_charge
                                    labor_extension = (reca.x_charge * self.product_uom_qty)
                                    if ((reca.x_charge * self.product_uom_qty) < labor_min_charge):
                                        labor_amount = labor_min_charge
                                    else:
                                        labor_amount = reca.x_charge * self.product_uom_qty
                                    val = {
                                        'x_product_product_labor':rec.x_labor_item.id,
                                        'x_product_description':rec.x_labor_item.x_Description,
                                        'x_product_labor_cu':rec.x_labor_item.x_customer_units,
                                        'x_labor_minimum':labor_min_charge,
                                        'x_labor_unit_value':labor_charge,
                                        'x_labor_extension':labor_extension,
                                        'x_labor_amount':labor_amount,
                                        'x_labor_unit_req':self.product_uom_qty
                                    }
                    else:
                        #_logger.info("Inside Else PRODUCT ID CHANGE")
                        val = {
                            'x_product_product_labor':rec.x_labor_item.id,
                            'x_product_description':rec.x_labor_item.x_Description,
                            'x_product_labor_select':rec.x_labor_item.x_customer_units,
                            #'x_labor_unit_req':self.product_uom_qty
                        }
                    res1.append((0,0,val))
            self.x_order_line_labor_items_grid_new = res1
            #_logger.info("Inside Else PRODUCT ID RES1'%s'",res1)
            if self.x_sale_line_item_group and self.x_order_line_embossing:
                product_ids = self.env['product.product'].search([('x_product_item', '=', self.x_sale_line_item_group.id),('x_item_width', '>=', self.x_customer_order_width),('x_product_product_embossing','=',self.x_order_line_embossing.id)]).ids
            else:
                product_ids = self.env['product.product'].search([('x_product_item', '=', self.x_sale_line_item_group.id),('x_item_width', '>=', self.x_customer_order_width)]).ids
            #_logger.info("Product IDS'%s'",product_ids)
            #product_ids_br = self.env['product.product'].browse(product_ids)
            if product_ids:
                for rec in product_ids:
                    widthouts = waste = lengthouts = 0
                    ad=bd=adw=bdw=bdw_frac_value=adl=bdl=mpsot=mssc=itemwidthAD=itemwidthBD=oms=wydr=wa=fwyd=itemwidthDisp=custqtymtr=0
                    waste_string=master_prod_sheet=''
                    wdp=wdow=0
                    calculated_width=new_width_out=0
                    product_ids_br = self.env['product.product'].browse(rec)
                    if product_ids_br and self.x_customer_order_width and self.x_customer_order_length>0.0:
                        #Width Outs
                        widthouts = (product_ids_br.x_item_width/self.x_customer_order_width)
                        ad,bd = math.modf(widthouts)
                        #Length Outs
                        lengthouts = (self.x_order_machine_length/self.x_customer_order_length)
                        adl,bdl=math.modf(lengthouts)
                        mpsot = (bd*bdl)
                        #self.x_order_line_master_out = mpsot
                        #Master Sheet Size Calculation
                        mssc = (bdl*self.x_customer_order_length) + self.x_product_order_trim_length
                        #self.x_order_line_master_sheet_length = mssc
                        #_logger.info("Master Sheet Size '%s'",mssc)
                        machine_stops_ids = self.env['machine.stops'].search([('x_machine_st', '>=', mssc)], limit=1)
                        #_logger.info("Machine Stops IDS'%s'",machine_stops_ids.x_machine_st)
                        itemwidthAD,itemwidthBD = math.modf(product_ids_br.x_item_width)
                        itemwidthDisp = math.trunc(itemwidthBD)
                        master_prod_sheet = str(int(itemwidthBD)) + '*' + str(machine_stops_ids.x_machine_st)
                        #machine_stops_ids_browsed = self.env['machine.stops'].browse(machine_stops_ids)
                        #_logger.info("Machine Stop Value'%s'",int(machine_stops_ids.x_machine_st))
                        #Waste
                        waste = product_ids_br.x_item_width - ((bd * self.x_customer_order_width) + self.x_product_order_trim_width)
                        if (waste<0.00000):
                            waste = 0.00000
                        #Wide Yards Calculation
                        if mpsot:
                            oms = (self.product_uom_qty / mpsot)
                            wydr = oms * (machine_stops_ids.x_machine_st/36)
                            wa = (wydr * self.x_product_order_waste) 
                            fwyd = math.ceil(wa+wydr)
                            #Waste Deviation
                            wdow = (bd*self.x_customer_order_width)
                            wdp = 1 - (wdow/itemwidthBD)

                    if product_ids_br and self.x_customer_order_width and self.x_customer_order_length == 0.0:
                        itemwidthAD,itemwidthBD = math.modf(product_ids_br.x_item_width)
                        itemwidthDisp = math.trunc(itemwidthBD)
                        widthouts = (product_ids_br.x_item_width/self.x_customer_order_width)
                        _logger.info("widthouts'%s'",widthouts)
                        # ad,bd = math.modf(widthouts)
                        #bd = int(widthouts)
                        if product_ids_br.x_item_width == self.x_customer_order_width:
                            calculated_width = self.x_customer_order_width
                        else: 
                            calculated_width = (self.x_customer_order_width * int(widthouts)) + self.x_product_order_trim_width
                        #_logger.info("Calculated width'%s'",calculated_width)
                        if calculated_width > product_ids_br.x_item_width:
                            new_width_out = int(widthouts) - 1
                            bd = new_width_out
                        else:
                            new_width_out = int(widthouts)
                            bd = new_width_out
                        
                        #_logger.info("new_width_out'%s'",new_width_out)
                        #Waste
                        waste = product_ids_br.x_item_width - ((self.x_customer_order_width * new_width_out) + self.x_product_order_trim_width)
                        if waste<0:
                            waste = 0.000
                        #_logger.info("Waste'%s'",waste)
                        mpsot = 0
                        master_prod_sheet = ''
                        waste_string = ''
                        #Units Required
                        if self.x_order_customer_uom.name == 'yds' and new_width_out>0:
                            fwyd = (self.product_uom_qty / new_width_out)
                            fwyd += (fwyd * self.x_product_order_waste)
                        if self.x_order_customer_uom.name == 'sqft' and new_width_out>0:
                            fwyd = (self.product_uom_qty*144/self.x_customer_order_width/36/new_width_out)
                            fwyd += (fwyd * self.x_product_order_waste)
                        if self.x_order_customer_uom.name == 'lft' and new_width_out>0:
                            fwyd = (self.product_uom_qty/3/new_width_out)
                            fwyd += (fwyd * self.x_product_order_waste)
                        if self.x_order_customer_uom.name == 'lbs' and new_width_out>0:
                            if self.x_customer_order_length == 0.0000:
                                customer_length = 36
                            if self.x_customer_order_width > 0.000 and customer_length > 0.000 and self.x_sale_line_item_group and self.x_sale_line_item_group.x_basis_size > 0.000 and self.x_sale_line_item_group.x_basis_weight > 0.000:
                                pounds = (self.x_customer_order_width * customer_length * self.x_sale_line_item_group.x_basis_weight * 2) / self.x_sale_line_item_group.x_basis_size
                                fwyd = (self.product_uom_qty * 1000) / int(pounds)
                                fwyd += (fwyd * self.x_product_order_waste)
                        if self.x_order_customer_uom.name == 'mtr' and new_width_out>0:
                            custqtymtr = (self.product_uom_qty * 1.0936)
                            fwyd = (custqtymtr / new_width_out)
                            fwyd += (fwyd * self.x_product_order_waste)

                    val1 = {
                        'x_product_product_bom':rec,
                        'x_product_product_width':itemwidthDisp,
                        'x_product_product_widthInt':int(itemwidthBD),
                        'x_unit_req':math.ceil(fwyd),
                        'x_product_width_outs':bd,
                        'x_waste_arrv_prc':waste,
                        'x_mps_out':mpsot,
                        'x_mps':master_prod_sheet
                    }
                    res2.append((0,0,val1))
            #_logger.warning("Res 2'%s'",res2)
            if self.x_customer_order_width > 0.0 and self.product_uom_qty > 0.0:
                self.x_order_line_bom = res2
                # for bom in self.x_order_line_bom:
                #     if bom.x_product_product_bom == self.product_id:
                #         # bom.write({'x_product_bom_select': True})
                #         self.update_units_required()
                #     else:
                        # bom.write({'x_product_bom_select': False})
        res = super(SaleOrderLine, self).product_id_change()
        return res



class ProductCommodityCodeLabor(models.Model):
    _inherit = 'product.commodity.code.labor'

    x_sale_order_labor_item = fields.Many2one('sale.order.line','Labor Items')

class SaleProductBom(models.Model):
    _name = "sale.product.bom"

    x_product_bom = fields.Many2one('product.template',"Item")
    x_product_product_bom =  fields.Many2one('product.product',"Item")
    x_product_bom_select = fields.Boolean('Select')
    x_product_product_width = fields.Float('Width')
    x_product_product_widthInt = fields.Integer('Item Width')
    x_product_width_outs = fields.Integer('Outs')
    x_mps = fields.Char('Master Prod Sheets')
    x_mps_out = fields.Integer('MPS OUT')
    x_waste_frac = fields.Char('Waste')
    x_waste_deviation = fields.Float('Waste Dev')
    x_waste_arrv_prc = fields.Float('Waste(Dec)',digits='EF Price')
    x_waste_prc = fields.Float('Waste %')
    x_unit_req = fields.Integer('Units Required')
    x_sale_order_mst = fields.Many2one('sale.order.line','Items')
    x_line_item_width = fields.Float(related='x_sale_order_mst.x_selected_item_width')


class SaleOrientation(models.Model):
    _name = "sale.orientation"

    name = fields.Char('Orientation')
    x_orientation_uom = fields.Many2one('uom.uom','UoM')

class SaleProductLabor(models.Model):
    _name = "sale.product.labor"

    x_product_labor_select = fields.Boolean('Select')
    x_product_labor_pr = fields.Boolean('In Pricelist',readonly=True)
    x_product_labor_cu = fields.Boolean('Use Customer Units',readonly=True)
    currency_id = fields.Many2one('res.currency',string="Currency")
    x_product_labor_order_line = fields.Many2one('sale.order.line'," Labor Item")
    x_product_product_labor =  fields.Many2one('labor.items',"Labor Items")
    x_product_description = fields.Char("Labor Description")
    x_labor_unit_req = fields.Integer('Units')
    x_labor_unit_value = fields.Float('Unit $',digits='EF Price')
    x_labor_minimum = fields.Float('Minimum')
    x_labor_extension = fields.Float('Actuals')
    x_labor_amount = fields.Float('Amount')
    x_labor_monetary_amount =  fields.Monetary(compute='_compute_labor_total_amount', string='Labor Amount', store=True)
    x_product_labor_nullify = fields.Boolean('Null')

    @api.onchange('x_product_labor_nullify')
    def labor_nullify(self):
        for rec in self:
            if rec.x_product_labor_nullify:
                rec.x_labor_amount = 0

    @api.onchange('x_labor_unit_value')
    def _onchange_x_labor_unit_value(self):
        for rec in self:
            if rec.x_labor_unit_value and rec.x_labor_unit_req:
                rec.x_labor_extension = rec.x_labor_unit_value * rec.x_labor_unit_req
                if rec.x_labor_extension < rec.x_labor_minimum:
                    rec.x_labor_amount = rec.x_labor_minimum
                else:
                    rec.x_labor_amount = rec.x_labor_extension

    @api.depends('x_labor_amount')
    def _compute_labor_total_amount(self):
        for rec in self:
            total = 0.0
            if rec.x_labor_amount and rec.x_product_labor_select:
                total += rec.x_labor_amount
            rec.x_labor_monetary_amount = total

    @api.onchange('x_product_labor_select','x_product_product_labor','x_product_labor_order_line.outs','x_product_labor_order_line.product_id','x_product_labor_order_line.x_order_master_yards')
    def labor_change(self):
        knives_flag = False
        knives_charge = 0.0000
        knives_final_charge = 0.0000
        for rec in self:
            if rec.x_product_labor_select:
                if rec.x_product_labor_order_line.outs<=6:
                    #_logger.info("Inside IFFFFF LABOR CHANGE")
                    labor_ids_br = self.env['labor.items'].browse(self.x_product_product_labor.id)
                    #_logger.info("Inside IFFFFF LABOR ID'%s'",labor_ids_br.id)
                    #rec.x_labor_unit_req = rec.x_product_labor_order_line.product_uom_qty
                    rec.x_labor_minimum = labor_ids_br.x_min_charge
                    if labor_ids_br.x_no_of_break_quantities_grid:
                        for reca in labor_ids_br.x_no_of_break_quantities_grid:
                            r1=r2=nameval=''
                            nameval = reca.name.split("-")
                            if ((rec.x_labor_unit_req >= int(nameval[0])) and (rec.x_labor_unit_req <= int(nameval[1]))): 
                                self.x_labor_unit_value = reca.x_charge
                                self.x_labor_extension = (reca.x_charge * rec.x_labor_unit_req)
                                if ((reca.x_charge * rec.x_labor_unit_req) < rec.x_labor_minimum):
                                    self.x_labor_amount = labor_ids_br.x_min_charge
                                else:
                                    self.x_labor_amount = reca.x_charge * rec.x_labor_unit_req
                else:
                    labor_ids_br = self.env['labor.items'].browse(self.x_product_product_labor.id)
                    #_logger.info("Inside IFFFFF LABOR ID'%s'",labor_ids_br.id)
                    #rec.x_labor_unit_req = rec.x_product_labor_order_line.product_uom_qty
                    rec.x_labor_minimum = labor_ids_br.x_min_charge
                    if labor_ids_br.x_m2_extra_knives:
                        for ek in labor_ids_br.x_m2_extra_knives.x_no_of_extra_knives_grid:
                            if ek.x_extra_knives_sub == rec.x_product_labor_order_line.outs:
                                knives_charge = ek.x_upcharge_sub
                                knives_flag = True
                            if knives_flag == True:
                                knives_final_charge = knives_charge
                                _logger.info("Inside IFFFFF EKKKKKKKKKKKKK FINALLL CHARGEE'%s'",knives_final_charge)
                                break
                    if labor_ids_br.x_no_of_break_quantities_grid:
                        for reca in labor_ids_br.x_no_of_break_quantities_grid:
                            r1=r2=nameval=''
                            nameval = reca.name.split("-")
                            if ((rec.x_labor_unit_req >= int(nameval[0])) and (rec.x_labor_unit_req <= int(nameval[1]))): 
                                self.x_labor_unit_value = (reca.x_charge + knives_final_charge)
                                self.x_labor_extension = ((reca.x_charge + knives_final_charge) * rec.x_labor_unit_req)
                                if ((reca.x_charge * rec.x_labor_unit_req) < rec.x_labor_minimum):
                                    self.x_labor_amount = labor_ids_br.x_min_charge
                                else:
                                    self.x_labor_amount = (reca.x_charge + knives_final_charge) * rec.x_labor_unit_req
                            #_logger.warning("Labor Range Charge'%s' ",reca.x_charge)
            else:
                _logger.info("Inside Else LABOR CHANGE")
                labor_ids_br = self.env['labor.items'].browse(self.x_product_product_labor.id)
                #rec.x_labor_unit_req = rec.x_product_labor_order_line.x_order_master_yards
                rec.x_labor_minimum = labor_ids_br.x_min_charge
                if labor_ids_br.x_no_of_break_quantities_grid:
                    for reca in labor_ids_br.x_no_of_break_quantities_grid:
                        r1=r2=nameval=''
                        nameval = reca.name.split("-")
                        if ((rec.x_labor_unit_req >= int(nameval[0])) and (rec.x_labor_unit_req <= int(nameval[1]))): 
                            self.x_labor_unit_value = reca.x_charge
                            self.x_labor_extension = (reca.x_charge * rec.x_labor_unit_req)
                            if ((reca.x_charge * rec.x_labor_unit_req) < rec.x_labor_minimum):
                                self.x_labor_amount = labor_ids_br.x_min_charge
                            else:
                                self.x_labor_amount = reca.x_charge * rec.x_labor_unit_req
                            #_logger.warning("Labor Range Charge'%s' ",reca.x_charge)

class SaleMultiSize(models.Model):
    _name = "sale.multi.size"

    x_order_outs = fields.Integer('Outs',digits='EF Price')
    x_order_size = fields.Float('Size',digits='EF Price')
    x_total_size = fields.Float('Total Size',digits='EF Price')
    x_order_size_ref = fields.Many2one('sale.order',"Slit sizes")
    x_order_line_size_ref = fields.Many2one('sale.order.line',"Slit sizes")
    x_line_item_multi_width = fields.Float(related='x_order_line_size_ref.x_selected_item_width')

    @api.onchange('x_order_outs','x_order_size')
    def _compute_total_size(self):
        for rec in self:
            if rec.x_order_outs>0 and rec.x_order_size > 0.0000:
                rec.x_total_size = (rec.x_order_outs * rec.x_order_size)

    # @api.model
    # def create(self):
    #     for rec in self:
    #         total_sum = sum(rec.x_total_size for rec in self)
    #         _logger.info("SUMMMMMMMM '%s'",total_sum)

    # @api.constrains('x_total_size', 'x_line_item_multi_width')
    # def _check_multi_line(self):
    #     for rec in self:
    #         _logger.info("SUMMMMMMMM ")
    #         total_sum = sum(rec.x_total_size for rec in self)
    #         _logger.info("SUMMMMMMMM '%s'",total_sum)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    so_order_approval = fields.Boolean("Sale Approval")
    so_limit = fields.Float(string="Amount limit requires approval")

    def set_values(self):
        """ save values in the settings employee fields"""
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].set_param(
            'ef_sales.so_order_approval',
            self.so_order_approval)
        self.env['ir.config_parameter'].set_param(
            'ef_sales.so_limit',
            self.so_limit)


    @api.model
    def get_values(self):
        """ Get values for employee fields in the settings
         and assign the value to that fields"""
        res = super(ResConfigSettings, self).get_values()
        params = self.env['ir.config_parameter'].sudo()
        res.update(
            so_limit=params.get_param('ef_sales.so_limit'),
            so_order_approval=params.get_param('ef_sales.so_order_approval'),
        ),
        return res