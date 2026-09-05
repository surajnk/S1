# -*- coding: utf-8 -*-

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    has_credits = fields.Boolean(
        string='Has Credits',
        compute='_compute_has_credits',
        store=False,
        readonly=True,
        help='Indicates whether the customer has credits that can be applied to this invoice.',
    )
    latest_delivery_date = fields.Datetime(
        string='Latest Delivery Date',
        compute='_compute_latest_delivery_date',
        store=True,
        readonly=True,
        help='Date of the latest delivery order completed for this invoice.',
    )
    email_invoice = fields.Boolean(
        string='Email Invoice?',
        help='Send the invoice to the customer when it is posted.',
    )

    def action_post(self):
        res = super().action_post()
        unposted_moves = self.filtered(lambda move: move.state != 'posted')
        if unposted_moves:
            unposted_moves._post(soft=False)
        template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
        if template:
            posted_moves = self.filtered(lambda move: move.email_invoice and move.state == 'posted')
            for move in posted_moves:
                template.send_mail(move.id, force_send=True)
        return res

    @api.depends(
        'move_type',
        'invoice_line_ids.sale_line_ids.order_id.picking_ids.state',
        'invoice_line_ids.sale_line_ids.order_id.picking_ids.date_done',
        'invoice_line_ids.sale_line_ids.order_id.picking_ids.location_dest_id.usage',
    )
    def _compute_latest_delivery_date(self):
        for invoice in self:
            if invoice.move_type != 'out_invoice':
                invoice.latest_delivery_date = False
                continue
            sale_orders = invoice.invoice_line_ids.sale_line_ids.order_id
            deliveries = sale_orders.mapped('picking_ids').filtered(
                lambda picking: picking.state == 'done'
                and picking.location_dest_id.usage == 'customer'
                and picking.date_done
            )
            latest_delivery = deliveries.sorted('date_done', reverse=True)[:1]
            invoice.latest_delivery_date = latest_delivery.date_done if latest_delivery else False

    @api.depends('partner_id', 'partner_id.credit')
    def _compute_has_credits(self):
        for invoice in self:
            invoice.has_credits = bool(invoice.partner_id and invoice.partner_id.credit < 0)

    @api.onchange('partner_id')
    def _onchange_partner_has_credits(self):
        for invoice in self:
            invoice.has_credits = bool(invoice.partner_id and invoice.partner_id.credit < 0)
