from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)

class OnOrderDetailWizard(models.TransientModel):
    _name = 'on.order.detail.wizard'
    _description = 'On Order Details'

    product_tmpl_id = fields.Many2one('product.template', 'Product', readonly=True)
    line_ids = fields.One2many('on.order.detail.line', 'wizard_id', 'Details')

    def _populate_lines(self):
        self.ensure_one()
        

        tmpl = self.product_tmpl_id
        tmpl_id = tmpl.id
        _logger.info("=== ON ORDER WIZARD: tmpl_id=%s name=%s ===", tmpl_id, tmpl.name)
        _logger.info("variant_ids=%s", tmpl.product_variant_ids.ids)

        lines = []

        mos = self.env['mrp.production'].search([
            ('state', 'in', ('confirmed', 'progress')),
            ('product_id.product_tmpl_id', '=', tmpl_id),
        ])
        _logger.info("MOs found: %s", mos.ids)
        for m in mos:
            _logger.info("  MO %s origin=%s qty=%s produced=%s active=%s",
                         m.name, m.origin, m.product_qty, m.qty_produced, m.product_id.active)

        po_lines = self.env['purchase.order.line'].search([
            ('order_id.state', 'in', ('purchase', 'done')),
            ('product_id.product_tmpl_id', '=', tmpl_id),
        ])
        _logger.info("PO lines found: %s", po_lines.ids)
        for l in po_lines:
            _logger.info("  POL %s state=%s qty=%s recv=%s active=%s",
                         l.order_id.name, l.order_id.state, l.product_qty,
                         l.qty_received, l.product_id.active)

        origins = list(set(mos.filtered(lambda m: m.origin).mapped('origin')))
        so_names = set(self.env['sale.order'].search([('name', 'in', origins)]).mapped('name'))
        _logger.info("SO-origins matched: %s", so_names)

        for m in mos:
            if m.origin and m.origin in so_names:
                continue
            qty = m.product_qty - m.qty_produced
            if qty > 0:
                lines.append((0, 0, {'order_type': 'mo', 'reference': m.name,
                                     'date_order': m.date_planned_start, 'qty': qty, 'state': m.state}))
        for l in po_lines:
            if l.product_qty <= 0:
                continue
            if l.converted_product_qty > 0:
                ordered_conv = l.converted_product_qty
            else:
                ordered_conv = l.product_uom._compute_quantity(
                    l.product_qty, l.product_id.uom_id)
            if ordered_conv <= 0:
                continue
            pending = max(l.product_qty - l.qty_received, 0.0)
            pending_conv = ordered_conv * (pending / l.product_qty) if l.product_qty else 0.0
            lines.append((0, 0, {
                'order_type': 'po',
                'reference': l.order_id.name,
                'date_order': l.order_id.required_date,
                'qty': ordered_conv,
                'pending_qty': pending_conv,
                'order_uom_id': l.product_uom.id,
                'state': l.order_id.state,
            }))
        # for l in po_lines:
        #     qty = l.product_qty - l.qty_received
        #     if qty > 0:
        #         lines.append((0, 0, {'order_type': 'po', 'reference': l.order_id.name,
        #                              'date_order': l.order_id.date_order, 'qty': qty, 'state': l.order_id.state}))

        _logger.info("LINES BUILT: %s", len(lines))
        self.line_ids = lines


    def _populate_ncr_lines(self):
        self.ensure_one()
        tmpl_id = self.product_tmpl_id.id
        lines = []

        ncr_lots = self.env['nrc.stock.lot'].search([
            ('stock_lot_id.product_id.product_tmpl_id', '=', tmpl_id),
        ])
        for nl in ncr_lots:
            qty = nl.quantity
            if qty > 0:
                ncr = nl.nrc_id
                lines.append((0, 0, {
                    'order_type': 'ncr',
                    'reference': ncr.name,
                    'lot_name': nl.stock_lot_id.name,
                    'date_order': False,
                    'qty': qty,
                    'state': ncr.status or '',
                }))

        self.line_ids = lines

    def _populate_lot_ncr_lines(self, lot_id):
        self.ensure_one()
        lines = []
        ncr_lots = self.env['nrc.stock.lot'].search([
            ('stock_lot_id', '=', lot_id),
            ('nrc_id.status', '=', 'open'),
        ])
        for nl in ncr_lots:
            if nl.quantity > 0:
                ncr = nl.nrc_id
                lines.append((0, 0, {
                    'order_type': 'ncr',
                    'reference': ncr.name,
                    'lot_name': nl.stock_lot_id.name,
                    'date_order': False,
                    'qty': nl.quantity,
                    'state': ncr.status or '',
                }))
        self.line_ids = lines

    def _populate_allocated_lines(self):
        self.ensure_one()
        tmpl_id = self.product_tmpl_id.id
        lines = []
        # Part A: component usage in open MOs (demand)
        raw_moves = self.env['stock.move'].search([
            ('raw_material_production_id', '!=', False),
            ('raw_material_production_id.state', 'in', ('confirmed', 'progress')),
            ('product_id.product_tmpl_id', '=', tmpl_id),
            ('state', 'not in', ('done', 'cancel')),
        ])
        for mv in raw_moves:
            qty = mv.product_uom_qty
            if qty > 0:
                mo = mv.raw_material_production_id
                lines.append((0, 0, {
                    'order_type': 'component',
                    'reference': mo.name,
                    'date_order': mo.date_planned_start,
                    'qty': qty,
                    'state': mo.state,
                }))
        # Part B: SO-originated MOs producing this product
        mos = self.env['mrp.production'].search([
            ('state', 'in', ('confirmed', 'progress')),
            ('product_id.product_tmpl_id', '=', tmpl_id),
        ])
        origins = list(set(mos.filtered(lambda m: m.origin).mapped('origin')))
        sale_orders = self.env['sale.order'].search([('name', 'in', origins)])
        so_map = {so.name: so for so in sale_orders}
        for m in mos:
            if m.origin and m.origin in so_map:
                qty = m.product_qty - m.qty_produced
                if qty > 0:
                    so = so_map[m.origin]
                    lines.append((0, 0, {
                        'order_type': 'mo',
                        'reference': m.name,
                        'date_order': m.date_planned_start,
                        'qty': qty,
                        'state': m.state,
                        'so_number': so.name,
                        'customer_id': so.partner_id.id,
                    }))
        self.line_ids = lines

    # def _populate_allocated_lines(self):
    #     self.ensure_one()
    #     tmpl_id = self.product_tmpl_id.id
    #     lines = []

    #     # Part A: component usage in open MOs (demand)
    #     raw_moves = self.env['stock.move'].search([
    #         ('raw_material_production_id', '!=', False),
    #         ('raw_material_production_id.state', 'in', ('confirmed', 'progress')),
    #         ('product_id.product_tmpl_id', '=', tmpl_id),
    #         ('state', 'not in', ('done', 'cancel')),
    #     ])
    #     for mv in raw_moves:
    #         qty = mv.product_uom_qty
    #         if qty > 0:
    #             mo = mv.raw_material_production_id
    #             lines.append((0, 0, {
    #                 'order_type': 'component',
    #                 'reference': mo.name,
    #                 'date_order': mo.date_planned_start,
    #                 'qty': qty,
    #                 'state': mo.state,
    #             }))

    #     # Part B: SO-originated MOs producing this product
    #     mos = self.env['mrp.production'].search([
    #         ('state', 'in', ('confirmed', 'progress')),
    #         ('product_id.product_tmpl_id', '=', tmpl_id),
    #     ])
    #     origins = list(set(mos.filtered(lambda m: m.origin).mapped('origin')))
    #     so_names = set(self.env['sale.order'].search(
    #         [('name', 'in', origins)]).mapped('name'))
    #     for m in mos:
    #         if m.origin and m.origin in so_names:
    #             qty = m.product_qty - m.qty_produced
    #             if qty > 0:
    #                 lines.append((0, 0, {
    #                     'order_type': 'mo',
    #                     'reference': m.name,
    #                     'date_order': m.date_planned_start,
    #                     'qty': qty,
    #                     'state': m.state,
    #                 }))

    #     self.line_ids = lines



class OnOrderDetailLine(models.TransientModel):
    _name = 'on.order.detail.line'
    _description = 'On Order Detail Line'

    wizard_id = fields.Many2one('on.order.detail.wizard', ondelete='cascade')
    order_type = fields.Selection([
        ('mo', 'Manufacturing Order'),
        ('po', 'Purchase Order'),
        ('component', 'MO Component'),
        ('ncr', 'NCR')], 'Type')
    reference = fields.Char('Reference')
    so_number = fields.Char('SO Number')
    customer_id = fields.Many2one('res.partner', 'Customer')
    lot_name = fields.Char('Lot')
    date_order = fields.Datetime('Date')
    qty = fields.Float('Ordered Qty', digits='Product Unit of Measure')
    order_uom_id = fields.Many2one('uom.uom', 'Ordered UoM')
    pending_qty = fields.Float('Pending Qty', digits='Product Unit of Measure')
    state = fields.Char('Status')