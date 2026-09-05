from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)

class CrmLeadProduct(models.Model):
    _name = 'crm.lead.product'
    
    product_id =  fields.Many2one('product.product',string='Product')
    description = fields.Text(string='Description')
    qty = fields.Float(string='Ordered Qty',default=1.0)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure')
    price_unit = fields.Float(string='Unit Price',store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes')
    lead_id = fields.Many2one('crm.lead')

    samples_domain = fields.Char(compute="_compute_samples", readonly=True, store=False, )

    @api.depends('samples_domain','product_id')
    def _compute_samples(self):
        product_list = []
        products_ids = self.env['product.product'].search([('categ_id.name', '=', 'Samples')])
        for rec in products_ids:
            product_list.append(rec.id)
        for rec in self:
            rec.samples_domain = json.dumps(
                [('id', 'in', product_list)]
            )
    
    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.default_code
            self.price_unit = 0
            self.product_uom = self.product_id.uom_id.id
            self.tax_id = self.product_id.taxes_id.ids

class CrmLead(models.Model):
    _inherit = 'crm.lead'
    
    lead_product_ids = fields.One2many('crm.lead.product','lead_id',string='Products For Quotation')
    quote_number =  fields.Char(string='Quote Number')

    def action_create_quotation(self):
        order_lines = []
        uomeasure_id = self.env['uom.uom'].search([('name', '=', 'Units')])
        price_id = self.env['product.pricelist'].search([('name', '=', 'Sample Pricelist')])

        #_logger.info("ORDER ID'%s'",self.order_ids)

        for line in self.lead_product_ids:
            order_lines.append((0,0,{'product_id': line.product_id.id,
                'name': line.description,
                'product_uom_qty':line.qty,
                'x_order_customer_uom':line.product_uom.id,
                'x_customer_order_width':0,
                'product_uom': line.product_uom.id,
                'price_unit': 0,
                'tax_id':[(6, 0, line.tax_id.ids)]
            }))
        if self.partner_id:
            res1 = self.env['sale.order'].create({
                'partner_id':self.partner_id.id,
                'team_id': self.team_id.id,
                'campaign_id': self.campaign_id.id,
                'medium_id': self.medium_id.id,
                'source_id': self.source_id.id,
                'opportunity_id': self.id,
                'x_is_sample':True,
                'pricelist_id':price_id.id,
                'order_line':order_lines,
            })
        else:
            raise UserError('In order to create sale order, Customer field should not be empty!')

        return {
            'name': "Create Sale Quotation",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sale.order',
            'target': 'current',
            'res_id':res1.id
            #'context': vals,
        }