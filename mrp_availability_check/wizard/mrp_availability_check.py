# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date


class MrpAvailabilityCheck(models.TransientModel):
    _name = "mrp.availability.check"
    _description = 'MRP Availability Check'

    bom_id = fields.Many2one("mrp.bom", 'Bill of Materials', required=True)
    product_id = fields.Many2one('product.product', 'Product', domain="[('type', '=', 'product')]", required=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', related='product_id.product_tmpl_id')
    requested_qty = fields.Float("Quantity", default=1.0, digits='Product Unit of Measure', required=True)
    product_uom_id = fields.Many2one("uom.uom", "UoM", related="product_id.uom_id")
    warehouse_id = fields.Many2one("stock.warehouse", 'Warehouse', required=True)
    location_id = fields.Many2one("stock.location", "Location", related="warehouse_id.lot_stock_id")
    line_ids = fields.One2many('mrp.bom.line.check', 'explosion_id')
    sum_line_ids = fields.One2many('mrp.bom.line.check.summarized', 'explosion_id')


    @api.onchange('product_id')
    def _onchange_product_id(self):
        for record in self:
            if record.product_id:
                record.bom_id = self.env['mrp.bom']._bom_find(product=record.product_id)

    def bom_explosion(self):
        self.ensure_one()

        def _create_bom_lines(bom, level=0, factor=self.requested_qty):
            level += 1
            for line in bom.bom_line_ids:
                self.env['mrp.bom.line.check'].create({
                    'product_id': line.product_id.id,
                    'bom_line': line.id,
                    'bom_level': level,
                    'product_qty': line.product_qty * factor,
                    'product_uom_id': line.product_uom_id.id,
                    'location_id': self.location_id.id,
                    'explosion_id': self.id,
                })
                line_boms = line.product_id.bom_ids
                boms = line_boms
                if boms:
                    line_qty = line.product_uom_id._compute_quantity(line.product_qty, boms[0].product_uom_id)
                    new_factor = factor * line_qty / boms[0].product_qty
                    _create_bom_lines(boms[0], level, new_factor)

        _create_bom_lines(self.bom_id)

    def do_bom_summarized(self):
        self.bom_explosion()
        boms_lines = self.env['mrp.bom.line.check'].search([])
        domain = [('explosion_id', '=', self.id),('product_type', '=', 'product')]
        summarized_bom_lines = boms_lines.read_group(domain, ['product_id', 'product_qty'], ['product_id'], lazy=True)
        for line in summarized_bom_lines:
            self.env['mrp.bom.line.check.summarized'].create({
                'product_id': line['product_id'][0],
                'product_qty': line['product_qty'],
                'location_id': self.location_id.id,
                'explosion_id': self.id,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Availability Check'),
            #'view_mode': 'form',
            'auto_search': True,
            'res_model': 'mrp.availability.check',
            #'view_id': self.env.ref('mrp_availability_check.mrp_availability_check_view_form2').id,
            'target': 'new',
            'views': [(self.env.ref('mrp_availability_check.mrp_availability_check_view_form2').id, "form")],
            'res_id': self.id,
        }


class BomLine(models.TransientModel):
    _name = "mrp.bom.line.check"
    _description = 'MRP Availability Check Bom Line'

    explosion_id = fields.Many2one('mrp.availability.check', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    bom_level = fields.Integer('BoM Level', readonly=True)
    product_qty = fields.Float('Requested Qty', readonly=True, digits='Product Unit of Measure')
    product_uom_id = fields.Many2one('uom.uom', 'UoM', readonly=True)
    bom_line = fields.Many2one("mrp.bom.line", "BoM line", readonly=True)
    bom_id = fields.Many2one("mrp.bom", "BoM", related='bom_line.bom_id', readonly=True)
    produce_delay = fields.Float('Manufacturing Lead Time', related='product_id.produce_delay', readonly=True)
    product_type = fields.Selection(string='Product_type', related='product_id.type', readonly=True)
    purchase_delay = fields.Float('Purchase Lead Time', compute="_get_purchase_delay", readonly=True)
    location_id = fields.Many2one("stock.location", "Location", readonly=True)
    Make = fields.Boolean("Make", compute="_check_make", readonly=True)
    MTO = fields.Boolean("MTO", compute="_check_mto", readonly=True)
    Buy = fields.Boolean("Buy", compute="_check_buy", readonly=True)
    reorder_point = fields.Boolean("Reorder Point", compute="_check_reorder_point", readonly=True)


    def _get_purchase_delay(self):
        today = date.today()
        for record in self:
            record.purchase_delay = 0.0
            supplier = self.env["product.supplierinfo"].search([('product_id', '=', record.product_id.id), ('date_start', '<=', today), ('date_end', '>', today)], limit=1)
            if supplier:
                record.purchase_delay = supplier.delay
                continue
            supplier = self.env["product.supplierinfo"].search([('product_id', '=', record.product_id.id)], limit=1)
            if supplier:
                record.purchase_delay = supplier.delay
                continue
            supplier = self.env["product.supplierinfo"].search([('product_tmpl_id', '=', record.product_id.product_tmpl_id.id), ('date_start', '<=', today), ('date_end', '>', today)], limit=1)
            if supplier:
                record.purchase_delay = supplier.delay
                continue
            supplier = self.env["product.supplierinfo"].search([('product_tmpl_id', '=', record.product_id.product_tmpl_id.id)], limit=1)
            if supplier:
                record.purchase_delay = supplier.delay

    def _check_reorder_point(self):
        for record in self:
            check_reorder_point = False
            reorder_points = self.env["stock.warehouse.orderpoint"].search([('product_id', '=', record.product_id.id)])
            if reorder_points:
                check_reorder_point = True
            record.reorder_point = check_reorder_point

    def _check_make(self):
        for record in self:
            product_routes = record.product_id.route_ids + record.product_id.categ_id.total_route_ids
            check_make = False
            warehouse_id = record.location_id.get_warehouse()
            wh_make_route = warehouse_id.manufacture_pull_id.route_id
            if wh_make_route and wh_make_route <= product_routes:
                check_make = True
            else:
                make_route = False
                try:
                    make_route = self.env['stock.warehouse']._find_global_route('mrp.route_warehouse0_manufacture', _('Manufacture'))
                except UserError:
                    pass
                if make_route and make_route in product_routes:
                    check_make = True
            record.Make = check_make

    def _check_mto(self):
        for record in self:
            product_routes = record.product_id.route_ids + record.product_id.categ_id.total_route_ids
            check_mto = False
            warehouse_id = record.location_id.get_warehouse()
            wh_mto_route = warehouse_id.mto_pull_id.route_id
            if wh_mto_route and wh_mto_route <= product_routes:
                check_mto = True
            else:
                mto_route = False
                try:
                    mto_route = self.env['stock.warehouse']._find_global_route('stock.route_warehouse0_mto', _('Make To Order'))
                except UserError:
                    pass
                if mto_route and mto_route in product_routes:
                    check_mto = True
            record.MTO = check_mto

    def _check_buy(self):
        for record in self:
            product_routes = record.product_id.route_ids + record.product_id.categ_id.total_route_ids
            check_buy = False
            warehouse_id = record.location_id.get_warehouse()
            wh_buy_route = warehouse_id.buy_pull_id.route_id
            if wh_buy_route and wh_buy_route <= product_routes:
                check_buy = True
            else:
                buy_route = False
                try:
                    buy_route = self.env['stock.warehouse']._find_global_route('purchase_stock.route_warehouse0_buy', _('Buy'))
                except UserError:
                    pass
                if buy_route and buy_route in product_routes:
                    check_buy = True
            record.Buy = check_buy


class BomLineSummarize(models.TransientModel):
    _name = "mrp.bom.line.check.summarized"
    _description = 'MRP Availability Check Bom Line Summarized'

    explosion_id = fields.Many2one('mrp.availability.check', readonly=True)
    product_id = fields.Many2one('product.product', 'Product', readonly=True)
    product_qty = fields.Float('Product Qty', readonly=True, digits='Product Unit of Measure')
    product_uom_id = fields.Many2one('uom.uom', 'UoM', related='product_id.uom_id', readonly=True)
    location_id = fields.Many2one("stock.location", "Location", readonly=True)
    qty_available_in_source_loc = fields.Float("On Hand Qty", compute="_compute_qty_in_source_loc", readonly=True)
    qty_virtual_in_source_loc = fields.Float("Available Qty", compute="_compute_qty_in_source_loc", readonly=True)
    qty_incoming_in_source_loc = fields.Float("Incoming Qty", compute="_compute_qty_in_source_loc", readonly=True)
    qty_outgoing_in_source_loc = fields.Float("Outgoing Qty", compute="_compute_qty_in_source_loc", readonly=True)
    qty_delta_in_source_loc = fields.Float("Forecast Qty", compute="_compute_net_qty", readonly=True)
    available = fields.Boolean("Available", compute="_compute_net_qty", readonly=True, default=False)


    def _compute_qty_in_source_loc(self):
        for record in self:
            if record.product_id.type == "product":
                product_quantities = record.product_id.with_context(location=record.location_id.id)._product_available()[record.product_id.id]
                qty_available = record.product_id.with_context(location=record.location_id.id)._product_available()[record.product_id.id]['qty_available']
                qty_virtual = record.product_id.with_context(location=record.location_id.id)._product_available()[record.product_id.id]['virtual_available']
                qty_incoming = record.product_id.with_context(location=record.location_id.id)._product_available()[record.product_id.id]['incoming_qty']
                qty_outgoing = record.product_id.with_context(location=record.location_id.id)._product_available()[record.product_id.id]['outgoing_qty']
                record.qty_available_in_source_loc = record.product_id.product_tmpl_id.uom_id._compute_quantity(qty_available, record.product_uom_id) or False
                record.qty_virtual_in_source_loc = record.product_id.product_tmpl_id.uom_id._compute_quantity(qty_virtual, record.product_uom_id) or False
                record.qty_incoming_in_source_loc = record.product_id.product_tmpl_id.uom_id._compute_quantity(qty_incoming, record.product_uom_id) or False
                record.qty_outgoing_in_source_loc = record.product_id.product_tmpl_id.uom_id._compute_quantity(qty_outgoing, record.product_uom_id) or False
            else:
                record.qty_available_in_source_loc = False
                record.qty_virtual_in_source_loc = False
                record.qty_incoming_in_source_loc = False
                record.qty_outgoing_in_source_loc = False

    @api.onchange('product_qty', 'qty_virtual_in_source_loc')
    def _compute_net_qty(self):
        for record in self:
            record.available = False
            record.qty_delta_in_source_loc = False
            if record.product_id.type == "product":
                record.qty_delta_in_source_loc = record.qty_virtual_in_source_loc - record.product_qty
            if record.qty_delta_in_source_loc >= 0.0 or record.product_id.type != "product":
                record.available = True
