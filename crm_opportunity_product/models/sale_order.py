# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    opportunity_id = fields.Many2one('crm.lead',string='Products For Quotation')   
    
    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        if res.x_is_sample:
            for line in res.order_line:
                line.price_unit = 0.0
        return res

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        if vals.get('x_is_sample'):
            if self.x_is_sample:
                for line in self.order_line:
                    line.price_unit = 0.0
        return res

    def _prepare_sale_order_lines_from_opportunity(self, record):
        data = {
                    'product_id':record.product_id.id,
                    'name':record.description,
                    'product_uom_qty':record.qty,
                    'product_uom':record.product_uom.id,
                    'price_unit':record.product_id.lst_price
                    }
        return data
    
    @api.onchange('opportunity_id')
    def opportunity_id_change(self):
        if not self.opportunity_id:
            return {}
        if not self.partner_id:
            self.partner_id = self.opportunity_id.partner_id.id

        new_lines = self.env['sale.order.line']
        for line in self.opportunity_id.lead_product_ids:

            data = self._prepare_sale_order_lines_from_opportunity(line)
            new_line = new_lines.new(data)
            new_lines += new_line

        self.order_line += new_lines
        return {}
    

