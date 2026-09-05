import datetime, time
from odoo import api, fields, models, tools, _
import logging
from odoo.tools import float_round
from pytz import timezone, UTC
from odoo.addons import decimal_precision as dp

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.depends('required_date')
    def _compute_date_planned(self):
        for order in self:
            if order.required_date:
                order.date_planned = fields.Datetime.to_datetime(order.required_date).replace(hour=12, minute=00,
                                                                                              second=00)
            else:
                order.date_planned = fields.Datetime.now()

    READONLY_STATES = {
        'purchase': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        states=READONLY_STATES,
        change_default=True,
        tracking=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id), ('supplier', '=', True)]",
        help="You can find a vendor by its Name, TIN, Email or Internal Reference. Only vendors with a supplier rank greater than 0 are selectable."
    )

    manual_po_number = fields.Char('Manual PO Number')
    consignment_po = fields.Boolean('Consignment PO')
    required_date = fields.Date('Required Date')
    freight_terms = fields.Many2one('account.incoterms', 'Freight Terms')
    freight_terms_id = fields.Many2one('freight.terms', 'Freight Terms')
    ship_via_id = fields.Many2one('ship.via', 'Ship Via')
    fob = fields.Selection([
        ('lunenburg', 'Lunenburg, MA 01462'),
        ('pawtucket', 'Pawtucket, RI 02861'),
        ('fac_boston', 'FCA Boston'),
        ('fac_newyork', 'FCA New York'),
        ('cerritos', 'Cerritos, CA 90703'),
        ('mill', 'Mill'),
    ], 'FOB', default='lunenburg')
    notes_comments = fields.Char('Notes(Comments)')
    sale_order_id = fields.Many2one('sale.order', 'Sale Order')
    contact_id = fields.Many2one('res.partner', string='Contact', domain="[('parent_id', '=', partner_id)]")
    ship_to = fields.Text(string="Ship To")

    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        if self.branch_id:
            self.ship_to = self.branch_id.address

    @api.model
    def create(self, vals):
        if vals.get('manual_po_number'):
            vals.update({'name': vals.get('manual_po_number')})
        res = super(PurchaseOrder, self).create(vals)
        if res.consignment_po:
            for line in res.order_line:
                line.price_unit = 0.0
        return res

    def write(self, vals):
        res = super(PurchaseOrder, self).write(vals)
        if vals.get('consignment_po'):
            if self.consignment_po:
                for line in self.order_line:
                    line.price_unit = 0.0
        return res

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            default_contact = self.partner_id.child_ids.filtered(lambda c: c.is_default_contact)
            self.contact_id = default_contact.id
            if self.partner_id.x_ship_via:
                self.ship_via_id = self.partner_id.x_ship_via
                self.freight_terms = self.partner_id.x_freight_terms
                self.payment_term_id = self.partner_id.property_supplier_payment_term_id
            elif self.partner_id.parent_id and self.partner_id.parent_id.x_ship_via:
                self.ship_via_id = self.partner_id.parent_id.x_ship_via
                self.freight_terms = self.partner_id.parent_id.x_freight_terms
                self.payment_term_id = self.partner_id.parent_id.property_supplier_payment_term_id
            if self.partner_id.ref:
                self.partner_ref = self.partner_id.ref
            elif self.partner_id.parent_id and self.partner_id.parent_id.ref:
                self.partner_ref = self.partner_id.ref

    def button_confirm(self):
        #_logger.info(">>> ENTER button_confirm override for PO IDs: %s", self.ids)
        try:
            res = super(PurchaseOrder, self).button_confirm()
            #_logger.info(">>> Returned from super().button_confirm() for PO IDs: %s", self.ids)
        except Exception as e:
            #_logger.exception("Error in super(PurchaseOrder,).button_confirm(): %s", e)
            # Re‐raise so Odoo’s RPC sees the exception and returns it to the client
            raise

        # Now run your custom loop
        for order in self:
            #_logger.info(">>> Processing custom logic for Purchase Order %s", order.name)
            try:
                # 1) find pickings by origin (stored field) and skip cancelled ones
                pickings = self.env['stock.picking'].search([
                    ('origin', '=', order.name),
                    ('state', 'not in', ('cancel',)),
                ])
                #_logger.info("    --> pickings found: %s", pickings.mapped('name'))

                if pickings:
                    for pick in pickings:
                        _logger.info("    --> processing Picking %s", pick.name)
                        for move in pick.move_ids_without_package:
                            _logger.info("        --> processing move %s (product %s)", move.id, move.product_id.display_name)
                            for supplierinfo in move.product_id.seller_ids:
                                partner = pick.partner_id
                                parent  = partner.parent_id
                                if supplierinfo.name.id not in (partner.id, parent.id):
                                    continue
                                if supplierinfo.x_product_convert_from_pur_uom <= 0.0:
                                    # _logger.info("            --> skipping supplierinfo %s because from_pur_uom = %s",
                                    #              supplierinfo.id,
                                    #              supplierinfo.x_product_convert_from_pur_uom)
                                    continue
                                # Compute converted_qty
                                converted_qty = (
                                    supplierinfo.x_product_convert_to_sku
                                    * (move.product_uom_qty / supplierinfo.x_product_convert_from_pur_uom)
                                )
                                # _logger.info("            --> converting move %s qty %s → %s",
                                #              move.id, move.product_uom_qty, converted_qty)
                                move.sudo().write({
                                    'product_uom_qty': converted_qty,
                                    'product_uom':     move.product_id.uom_id.id,
                                    'is_convert_ibs_yrd': True,
                                })
                                # _logger.info("            --> write complete for move %s", move.id)
                                # Stop scanning other seller_ids once converted
                                break

                # 2) Remove zero-conversion supplierinfo lines
                for line in order.order_line:
                    for seller in line.product_id.seller_ids:
                        if (
                            seller.name.id == order.partner_id.id
                            and seller.x_product_convert_from_pur_uom == 0.0
                            and seller.x_product_convert_to_sku == 0.0
                        ):
                            # _logger.info("    --> unlinking supplierinfo %s (product %s)", 
                            #              seller.id, line.product_id.display_name)
                            seller.unlink()

            except Exception as inner_e:
                _logger.exception("Error in custom loop for PO %s: %s", order.name, inner_e)
                # optionally continue to next order or re-raise; here we continue
                continue

        _logger.info(">>> EXIT button_confirm override for PO IDs: %s", self.ids)
        return res

    # def button_confirm(self):
    #     res = super(PurchaseOrder, self).button_confirm()
    #     picking_id = self.env['stock.picking'].search([('origin', '=', self.name)])
    #     if picking_id:
    #         for move in picking_id.move_ids_without_package:
    #             for product_supplier in move.product_id.seller_ids:
    #                 if product_supplier.name.id == picking_id.partner_id.id or product_supplier.name.id == picking_id.partner_id.parent_id.id:
    #                     if product_supplier.x_product_convert_from_pur_uom > 0.0:
    #                         converted_qty = product_supplier.x_product_convert_to_sku * (
    #                                     move.product_uom_qty / product_supplier.x_product_convert_from_pur_uom)
    #                         move.sudo().write({'product_uom_qty': converted_qty, 'product_uom': move.product_id.uom_id,
    #                                            'is_convert_ibs_yrd': True})
    #     for line in self.order_line:
    #         for seller in line.product_id.seller_ids:
    #             if seller.name.id == line.order_id.partner_id.id and seller.x_product_convert_from_pur_uom == 0.0 and seller.x_product_convert_to_sku == 0.0:
    #                 seller.unlink()
    #     return res


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    required_date = fields.Date('Required Date', related='order_id.required_date')
    notes_comments = fields.Char('Notes(Comments)')
    price_unit = fields.Float(string="Unit Price", digits=dp.get_precision('EF Price'))
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', domain="[('x_frequent_purchase', '=', True)]")
    customer_ref = fields.Char(string='Customer Reference')
    default_product_uom = fields.Many2one(
        'uom.uom',
        string='Stock UoM',
        compute='_compute_default_product_uom',
        store=True
    )

    converted_product_qty = fields.Float(
        string='Conv. Qty',
        digits='EF Price',
        compute='_compute_converted_product_qty',
        store=True,
        copy=False,
    )

    invoice_ids_1 = fields.Many2many('account.move', string='Bills', copy=False, store=True,
                                   compute="_compute_invoice")

    @api.depends('invoice_lines.move_id')
    def _compute_invoice(self):
        for order in self:
            invoices = order.mapped('invoice_lines.move_id')
            order.invoice_ids_1 = invoices

    remaining_quantity = fields.Float(string="Remaining Qty", compute='_compute_remaining_qty')
    picking_ids_1 = fields.Many2many('stock.picking', compute='_compute_picking', string='Receptions', copy=False,
                                   store=True)

    @api.depends('move_ids.picking_id')
    def _compute_picking(self):
        for order in self:
            pickings = order.mapped('move_ids.picking_id')
            order.picking_ids_1 = pickings


    @api.depends('product_qty', 'qty_received')
    def _compute_remaining_qty(self):
        for rec in self:
            rec.remaining_quantity = rec.product_qty - rec.qty_received

    @api.depends('product_qty', 'product_id', 'order_id.partner_id')
    def _compute_converted_product_qty(self):
        for line in self:
            converted_qty = 0.0
            if line.product_id and line.product_qty:
                for seller in line.product_id.seller_ids:
                    if seller.name and (seller.name.id == line.order_id.partner_id.id or
                                        (
                                                line.order_id.partner_id.parent_id and seller.name.id == line.order_id.partner_id.parent_id.id)):
                        if seller.x_product_convert_from_pur_uom > 0.0:
                            converted_qty = seller.x_product_convert_to_sku * (
                                    line.product_qty / seller.x_product_convert_from_pur_uom
                            )
                            break
            line.converted_product_qty = converted_qty


    def _get_ef_conversion_seller(self):
        self.ensure_one()
        partner = self.order_id.partner_id
        parent = partner.parent_id
        for seller in self.product_id.seller_ids:
            if seller.name.id in (partner.id, parent.id) and \
                    seller.x_product_convert_from_pur_uom > 0.0 and \
                    seller.x_product_convert_to_sku > 0.0:
                return seller
        return self.env['product.supplierinfo']

    @api.depends('move_ids.state', 'move_ids.quantity_done', 'move_ids.is_convert_ibs_yrd')
    def _compute_qty_received(self):
        converted_lines = self.filtered(
            lambda l: l.move_ids.filtered(lambda m: m.is_convert_ibs_yrd)
        )
        super(PurchaseOrderLine, self - converted_lines)._compute_qty_received()

        for line in converted_lines:
            seller = line._get_ef_conversion_seller()
            total = 0.0
            for move in line.move_ids.filtered(
                    lambda m: m.product_id == line.product_id and m.state == 'done'):
                qty_stock_uom = move.quantity_done
                if move.location_dest_id.usage == 'supplier':
                    # goods sent back to the vendor
                    if move.to_refund:
                        total -= qty_stock_uom
                else:
                    total += qty_stock_uom

            if seller:
                total = total * (seller.x_product_convert_from_pur_uom / seller.x_product_convert_to_sku)

            line._track_qty_received(total)
            line.qty_received = total

    @api.depends('product_id')
    def _compute_default_product_uom(self):
        for line in self:
            line.default_product_uom = line.product_id.uom_id if line.product_id else False

    def _get_product_purchase_description(self, product_lang):
        self.ensure_one()
        name = " "
        if product_lang.description_purchase:
            name = product_lang.description_purchase

        return name

    def _product_id_change(self):
        self.customer_ref = self.product_id.x_ExtReference
        self.notes_comments = self.product_id.default_code
        return super(PurchaseOrderLine, self)._product_id_change()

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            _logger.info("Selected Product Default Code: %s", self.product_id.default_code)
            self.name = self.product_id.default_code

    @api.onchange('product_id', 'product_qty')
    def onchange_product_product_qty(self):
        if self.product_id:
            for seller in self.product_id.seller_ids:
                if seller.purchase_product_break_codes_id:
                    for break_code in seller.purchase_product_break_codes_id.purchase_product_break_codes_line:
                        if break_code.break_qty:
                            split_break_code = break_code.break_qty.strip().split("-")

                            # Ensure valid format before proceeding
                            if len(split_break_code) == 2:
                                try:
                                    min_qty = int(split_break_code[0].strip())
                                    max_qty = int(split_break_code[1].strip())

                                    _logger.info("SPLIT CODE: %s", split_break_code)
                                    _logger.info("MIN QTY: %s", min_qty)
                                    _logger.info("MAX QTY: %s", max_qty)

                                    if min_qty <= self.product_qty <= max_qty:
                                        self.price_unit = break_code.selling_price
                                except ValueError as e:
                                    _logger.error("Error converting break_qty values to int: %s | Data: %s", e,
                                                  break_code.break_qty)
                            else:
                                _logger.warning("Invalid break_qty format (not exactly two elements): %s",
                                                break_code.break_qty)
                        else:
                            _logger.warning("break_qty is empty for record: %s", break_code)
                        # split_break_code = break_code.break_qty.split("-")
                        # _logger.info("SPLITTT CODEE '%s'",split_break_code)
                        # _logger.info("SPLITTT CODEE 0000 '%s'",int(split_break_code[0]))
                        # _logger.info("SPLITTT CODEE 1111 '%s'",int(split_break_code[1]))
                        # if ((self.product_qty >= int(split_break_code[0])) and (self.product_qty <= int(split_break_code[1]))):
                        #     self.price_unit = break_code.selling_price

    @api.model
    def _get_date_planned(self, seller, po=False):
        """Return the datetime value to use as Schedule Date (``date_planned``) for
           PO Lines that correspond to the given product.seller_ids,
           when ordered at `date_order_str`.

           :param Model seller: used to fetch the delivery delay (if no seller
                                is provided, the delay is 0)
           :param Model po: purchase.order, necessary only if the PO line is
                            not yet attached to a PO.
           :rtype: datetime
           :return: desired Schedule Date for the PO line
        """
        date_order = po.date_planned if po else self.order_id.date_planned
        if date_order:
            date_planned = fields.Datetime.to_datetime(date_order).replace(hour=17, minute=30, second=0)
        else:
            date_planned = datetime.today()
        return date_planned
