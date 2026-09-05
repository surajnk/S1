# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import models, fields, api, _

class SaleOrderLine(models.Model):   
    _inherit = "sale.order.line"
    
    order_ref = fields.Char('Order Reference',related='order_id.name')   
    customer_id = fields.Many2one('res.partner',related='order_id.partner_id')
    confirm_date = fields.Date('Confirmed Date')
    request_date = fields.Date('Requested Date',related='order_id.x_order_custom_del_date')
    line_customer_ref = fields.Char('Cust P.O', related='order_id.client_order_ref')

    delivery_dates_button = fields.Boolean(compute='_compute_delivery_dates_button', store=True)

    x_production_id = fields.Many2one(
        "mrp.production",
        string="Production Order",
        compute="_compute_production_id",
        store=False
    )

    @api.depends("order_id.procurement_group_id")
    def _compute_production_id(self):
        for line in self:
            production = self.env["mrp.production"].search([
                ("origin", "=", line.order_id.name),
                ("product_id", "=", line.product_id.id)
            ], limit=1)
            line.x_production_id = production

    def action_view_delivery_dates(self):
        """Action to view delivery dates for the product in the sale order line."""
        self.ensure_one()
        delivery_orders = self.env['stock.picking'].search([
            ('sale_id', '=', self.order_id.id),
            ('state', '=', 'done'),
            ('move_lines.product_id', '=', self.product_id.id)
        ])
        
        if not delivery_orders:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Deliveries Found'),
                    'message': _('There are no completed deliveries for this product.'),
                    'type': 'warning',
                },
            }
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Dates'),
            'view_mode': 'list',
            'res_model': 'stock.picking',
            'domain': [('id', 'in', delivery_orders.ids)],
            'target': 'new',
        }

    @api.depends('order_id', 'product_id')
    def _compute_delivery_dates_button(self):
        """Compute whether the delivery dates button should be visible."""
        for line in self:
            delivery_orders = self.env['stock.picking'].search_count([
                ('sale_id', '=', line.order_id.id),
                ('state', '=', 'done'),
                ('move_lines.product_id', '=', line.product_id.id)
            ])
            line.delivery_dates_button = delivery_orders > 0
