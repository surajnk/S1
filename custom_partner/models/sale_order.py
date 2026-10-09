from odoo import models, fields, api
from odoo.tools import float_round
import math
import base64
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_attachment = fields.Many2many('ir.attachment', string="Attachment", compute="_compute_partner_attachment")

    proforma_order_line_ids = fields.One2many(
        comodel_name='sale.order.line',
        inverse_name='order_id',
        string='Proforma Order Lines',
    )

    def action_approve(self):
        for order in self:
            # Set the state
            order.state = 'approve'
            order.approved = True
            # Generate the PDF report
            pdf_content, _ = order.env.ref('ef_sales.action_report_sale_custom_order')._render_qweb_pdf(order.id)
            attachment = order.env['ir.attachment'].create({
                'name': f'Sales Order - {order.name}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'res_model': 'sale.order',
                'res_id': order.id,
                'mimetype': 'application/pdf'
            })

            partner = order.partner_id

            # Get recipients
            manager = order.partner_id.x_manager  # Assuming partner manager is the user_id of the partner
            sales_rep = order.user_id
            recipient_ids = []

            if manager.id != self.env.user.id:  # Avoid sending to self
                recipient_ids.append(manager.partner_id.id)
            if sales_rep != self.env.user.id:
                recipient_ids.append(sales_rep.partner_id.id)
            if partner:
                recipient_ids.append(partner.id)

            if not recipient_ids:
                raise UserError("No valid recipients (partner manager or sales rep) found.")

            # Create the email
            template = order.env['mail.mail'].create({
                'subject': f'Sales Order Approved: {order.name}',
                'body_html': f"""
                    <p>Hello,</p>
                    <br></br>
                    <p>The sales order <strong>{order.name}</strong> has been approved.</p>
                    <p><a href="{order.get_portal_url()}">View Order in Odoo</a></p>
                    <br></br>
                    <p>Regards,<br/>Odoo System</p>
                """,
                'email_to': ','.join([partner.email for partner in order.env['res.partner'].browse(recipient_ids) if partner.email]),
                'attachment_ids': [(6, 0, [attachment.id])],
            })

            template.send()

        return True

    def action_quotation_send(self):
        self.ensure_one()

        template_id = self._find_mail_template()
        lang = self.env.context.get('lang')
        template = self.env['mail.template'].browse(template_id)
        if template.lang:
            lang = template._render_lang(self.ids)[self.id]
        template.write({
            'attachment_ids': [(5, 0, 0)],  # Clear all existing attachments
            'report_template': False,  # Prevent default report attachment
        })

        # 1. Render PDF from custom report
        report = self.env.ref('custom_partner.action_report_pro_forma_invoice_sale')
        pdf_content, _ = report._render_qweb_pdf(self.ids)

        # 2. Create attachment
        filename = f"{self.name}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'store_fname': filename,
            'res_model': 'sale.order',
            'res_id': self.id,
            'mimetype': 'application/pdf'
        })
        template.attachment_ids = False
        template.attachment_ids = [(6, 0, [attachment.id])]
        # 3. Launch email wizard with attachment
        ctx = {
            'default_model': 'sale.order',
            'default_res_id': self.id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'custom_layout': "mail.mail_notification_paynow",
            'proforma': self.env.context.get('proforma', False),
            'force_email': True,
            'model_description': self.with_context(lang=lang).type_name,

        }

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    @api.depends('partner_id')
    def _compute_partner_attachment(self):
        for order in self:
            partner = order.partner_id
            if partner.parent_id and not partner.partner_attachment:
                partner = partner.parent_id
            order.partner_attachment = partner.partner_attachment.ids


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    skid_ids = fields.One2many('skid.values', 'sale_order_line_id', string='Skid Values')
    sheet_allowance = fields.Char(string='Sheet Allowance')
    grain = fields.Char(string='Grain')
    x_class_commodity_group = fields.Many2one('product.commodity.code', 'Commodity Code',
                                              related='product_id.x_class_commodity_group')
    freight_amount = fields.Float(string='Freight Amount')
    dei_comment = fields.Char(string='DEI Comment')
    display_description = fields.Char(
        string='Display Description',
        compute='_compute_display_description',
    )

    product_attachment = fields.Many2many('ir.attachment', string="Attachment", related="product_id.product_attachment")
    meterial_weight_per_unit = fields.Float(string='Wt of 1 Unit', compute='_compute_meterial_weight')
    meterial_weight = fields.Float(string='Material Weight', compute='_compute_meterial_weight')
    kg_for_net_weight = fields.Float(string='KG for Net Weight', compute='_compute_meterial_weight')
    kg_for_gross_weight = fields.Float(string='KG for Gross Weight', compute='_compute_meterial_weight')


    # @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    # def _compute_amount(self):
    #     """
    #     Compute the amounts of the SO line.
    #     """
    #     for line in self:
    #         price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
    #         taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty,
    #                                         product=line.product_id, partner=line.order_id.partner_shipping_id)
    #         line.update({
    #             'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
    #             'price_total': taxes['total_included'],
    #             'price_subtotal': taxes['total_excluded'],
    #         })

    #         if taxes['total_included'] > 5000:
    #             if line.order_id.state not in ['hc', 'ch', 'mh', 'dh', 'sh']:
    #                 line.order_id.write({
    #                     'state': 'approve',
    #                 })

    def action_quotation_send_line(self):
        self.ensure_one()

        template_id = self.order_id._find_mail_template()
        lang = self.env.context.get('lang')
        template = self.env['mail.template'].browse(template_id)

        if template.lang:
            lang = template._render_lang([self.order_id.id])[self.order_id.id]  # Fixed to use order_id

        template.write({
            'attachment_ids': [(5, 0, 0)],
            'report_template': False,
        })

        # Render PDF from custom report (uses self.id = sale.order.line)
        report = self.env.ref('custom_partner.action_report_pro_forma_invoice_line')
        pdf_content, _ = report._render_qweb_pdf([self.id])

        filename = f"{self.name}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'store_fname': filename,
            'res_model': 'sale.order',
            'res_id': self.order_id.id,  # Fixed: attach to order not line
            'mimetype': 'application/pdf'
        })

        template.attachment_ids = [(6, 0, [attachment.id])]

        # Fixed: context and model set to order
        ctx = {
            'default_model': 'sale.order',
            'default_res_id': self.order_id.id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'mark_so_as_sent': True,
            'custom_layout': "mail.mail_notification_paynow",
            'proforma': self.env.context.get('proforma', False),
            'force_email': True,
            'model_description': self.order_id.with_context(lang=lang).type_name,
        }

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    @api.depends('x_customer_order_width', 'x_customer_order_length', 'product_uom', 'product_id', 'skid_ids',
                 'x_customer_order_width_mm', 'x_customer_order_length_mm')
    def _compute_meterial_weight(self):
        for rec in self:
            # Check if UoM is yards

            width = rec.x_customer_order_width or 0.0
            length = rec.x_customer_order_length or 0.0

            basic_size = rec.product_id.x_product_item.x_basis_size or 1.0  # prevent division by zero
            basic_weight = rec.product_id.x_product_item.x_basis_weight or 0.0

            meterial_weight = (width * length) / basic_size
            group_weight = meterial_weight * basic_weight
            meterial_weight = math.floor(group_weight * 0.002 * 100) / 100
            rec.meterial_weight_per_unit = math.floor(meterial_weight * 100) / 100

            qty = rec.product_uom_qty or 0.0
            rec.meterial_weight = rec.meterial_weight_per_unit * qty
            rec.kg_for_net_weight = (rec.meterial_weight or 0.0) / 2.20462

            skid_weight = sum(rec.skid_ids.mapped('skid_total_wight') or [0.0])
            rec.kg_for_gross_weight = (skid_weight + (rec.meterial_weight or 0.0)) / 2.20462

    @api.depends('x_customer_order_width', 'x_customer_order_length', 'product_uom', 'product_id', 'order_id')
    def _compute_display_description(self):
        for line in self:
            width = line.x_customer_order_width or 0
            length = line.x_customer_order_length or 0
            uom = line.product_uom.name or ''
            product = line.product_id.name or ''
            # Use multiplication sign × instead of *
            line.display_description = f"{uom} / {width:g} × {length:g} - {product}"

    def download_proforma_line(self):
        return self.env.ref('custom_partner.action_report_pro_forma_invoice_line').report_action(self)


class SkidValues(models.Model):
    _name = 'skid.values'

    number_of_skids = fields.Integer(string='Number of Skids')
    skid_height = fields.Float(string='Skid Height')
    skid_width = fields.Float(string='Skid Width')
    skid_length = fields.Float(string='Skid Length')
    skid_weight = fields.Float(string='Skid Weight')
    skid_total_wight = fields.Float(string='Total Skid Weight', compute='_compute_skid_total_weight')
    sale_order_line_id = fields.Many2one('sale.order.line', string='Sale Order Line')
    packaging_id = fields.Many2one('product.packaging', string='Packaging')

    @api.onchange('packaging_id')
    def _onchange_packaging_id(self):
        for skid in self:
            if skid.packaging_id:
                skid.skid_width = skid.packaging_id.width
                skid.skid_length = skid.packaging_id.packaging_length
                skid.skid_weight = skid.packaging_id.max_weight
            else:
                skid.skid_height = 0
                skid.skid_width = 0
                skid.skid_length = 0
                skid.skid_weight = 0

    @api.depends('skid_weight', 'number_of_skids')
    def _compute_skid_total_weight(self):
        for skid in self:
            skid.skid_total_wight = skid.number_of_skids * skid.skid_weight
