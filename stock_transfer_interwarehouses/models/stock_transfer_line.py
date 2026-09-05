# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime


class StockMove(models.Model):
    _inherit = "stock.move"

    stock_transfer_line_id = fields.Many2one('stock.transfer.line', 'Stock Transfer Line', index=True)


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _get_custom_move_fields(self):
        fields = super(StockRule, self)._get_custom_move_fields()
        fields += ['stock_transfer_line_id']
        return fields


class StockTransferLine(models.Model):
    _name = 'stock.transfer.line'
    _description = 'Stock Transfer Document Lines'
    _order = 'stock_transfer_id, sequence, id'

    READONLY_STATES = {
        'confirm': [('readonly', True)],
        'progress': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    name = fields.Text(string='Description', required=True, states=READONLY_STATES)
    sequence = fields.Integer('Sequence', default=10)
    stock_transfer_id = fields.Many2one('stock.transfer', string='Stock Transfer Reference', index=True, required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='stock_transfer_id.company_id', string='Company', store=True)
    state = fields.Selection(related='stock_transfer_id.state', store=True)
    product_id = fields.Many2one('product.product', 'Product', required=True, states=READONLY_STATES)
    product_qty = fields.Float('Quantity', digits='Product Unit of Measure', default=1.0, required=True, states=READONLY_STATES)
    product_uom_qty = fields.Float('Total Quantity', compute='_compute_product_uom_qty', store=True)
    product_uom = fields.Many2one('uom.uom', string='Unit of Measure', required=True, domain="[('category_id', '=', product_uom_category_id)]")
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    date_planned = fields.Datetime('Receipt Date', related='stock_transfer_id.date_planned', store=True)

    route_id = fields.Many2one("stock.location.route", "Route")
    move_ids = fields.One2many('stock.move', 'stock_transfer_line_id', string='Stock Moves')
    qty_received = fields.Float("Received Qty", compute='_compute_qty_received', compute_sudo=True, store=True, digits='Product Unit of Measure')
    qty_to_deliver = fields.Float("Qty to Deliver", compute='_compute_qty_to_deliver', compute_sudo=True, store=True, digits='Product Unit of Measure')
    qty_delivered = fields.Float("Delivered Qty", compute='_compute_qty_delivered', compute_sudo=True, store=True, digits='Product Unit of Measure')


    @api.depends('move_ids.move_orig_ids.state')
    def _compute_qty_to_deliver(self):
        for line in self:
            moves = line.move_ids.move_orig_ids.filtered(lambda x: x.state not in ("done", "cancel"))
            line.qty_to_deliver = sum(moves.mapped('product_uom_qty'))

    @api.depends('move_ids.move_orig_ids.state')
    def _compute_qty_delivered(self):
        for line in self:
            moves = line.move_ids.move_orig_ids.filtered(lambda x: x.state == "done")
            line.qty_delivered = sum(moves.mapped('quantity_done'))

    @api.depends('move_ids.state')
    def _compute_qty_received(self):
        for line in self:
            moves = line.move_ids.filtered(lambda x: x.state == "done")
            line.qty_received = sum(moves.mapped('quantity_done'))

    def _get_route(self):
        for line in self:
            rule_receipt = self.env['stock.rule'].search([
                ('location_id', '=', line.stock_transfer_id.location_id.id),
                ('location_src_id', '=', line.stock_transfer_id.company_id.internal_transit_location_id.id),
                ('warehouse_id', '=', line.stock_transfer_id.warehouse_id.id),
                ('propagate_warehouse_id', '=', line.stock_transfer_id.source_warehouse_id.id)], limit=1)
            if not rule_receipt:
                raise UserError(_('Transfer not allowed; please check the warehouses setting where the resupply chain has been defined.'))
            line.route_id = rule_receipt.route_id
        return True

    def run_procurement(self):
        for line in self:
            values = {
            'date_planned': line.stock_transfer_id.date_planned,
            'warehouse_id': line.stock_transfer_id.warehouse_id,
            'group_id': line.stock_transfer_id.group_id,
            'stock_transfer_line_id': line.id,
            'route_ids': line.route_id,
            }
            self.env['procurement.group'].run([self.env['procurement.group'].Procurement(
                    line.product_id,
                    line.product_qty,
                    line.product_uom,
                    line.stock_transfer_id.location_id,
                    line.stock_transfer_id.name,
                    line.stock_transfer_id.name,
                    line.stock_transfer_id.company_id,
                    values)], raise_user_error=True)
        return True

    def unlink(self):
        for line in self:
            if line.stock_transfer_id.state in ['confirm', 'done']:
                raise UserError(_('Cannot delete a stock transfer line in state \'%s\'.') % (line.state,))
        return super().unlink()

    @api.depends('product_uom', 'product_qty', 'product_id.uom_id')
    def _compute_product_uom_qty(self):
        for line in self:
            if line.product_id and line.product_id.uom_id != line.product_uom:
                line.product_uom_qty = line.product_uom._compute_quantity(line.product_qty, line.product_id.uom_id)
            else:
                line.product_uom_qty = line.product_qty

    @api.onchange('product_id')
    def onchange_product_id(self):
        if not self.product_id:
            return
        self.product_uom = self.product_id.uom_id
        self.product_qty = 1.0
        lang_code = self.env.lang
        product_lang = self.product_id.with_context(
            lang=lang_code,
            company_id=self.company_id.id)
        self.name = product_lang.display_name

    @api.onchange('product_qty')
    def onchange_product_qty(self):
        if not self.product_qty > 0.0:
            raise UserError(_('Quantity has to be positive.'))