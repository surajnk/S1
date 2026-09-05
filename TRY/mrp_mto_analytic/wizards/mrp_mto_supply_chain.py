# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date


class MrpMtoSupplyChain(models.TransientModel):
    _name = "mrp.mto.supply.chain"
    _description = 'MRP MTO Supply Chain Report'

    sale_id = fields.Many2one("sale.order", 'Sales Order', required=True)
    #sale_line_id = fields.Many2one("sale.order.line", 'Sales Order Item', required=True, domain=[('order_id', '=', sale_id)])
    customer_id = fields.Many2one('res.partner', string='Customer', readonly=True, related='sale_id.partner_id')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', readonly=True, related='sale_id.analytic_account_id')
    user_id = fields.Many2one('res.users', string='Responsible', readonly=True, related='sale_id.user_id')
    line_ids = fields.One2many('mrp.mto.supply.chain.line', 'explosion_id')
    line_mo_ids = fields.One2many('mrp.mto.supply.chain.line.mo', 'explosion_id')
    line_po_ids = fields.One2many('mrp.mto.supply.chain.line.po', 'explosion_id')

    #@api.onchange('sale_id')
    #def _onchange_sale_id(self):
    #    for record in self:
    #        if record.sale_id:
    #            return {'domain': {'sale_line_id': [('order_id', '=', self.sale_id.id)]}}

    def _create_mos(self, source, level, child_mos):
        for child_mo in child_mos:
            self.env['mrp.mto.supply.chain.line.mo'].create({
                'product_id': child_mo.product_id.id,
                'manufacture_id': child_mo.id,
                'level': level,
                'mo_state': child_mo.state,
                'source': source,
                'product_qty': child_mo.product_qty,
                'qty_producing': child_mo.qty_producing,
                'product_uom_id': child_mo.product_uom_id.id,
                'date_planned_start_pivot': child_mo.date_planned_start_pivot,
                'date_planned_finished_pivot': child_mo.date_planned_finished_pivot,
                'reservation_state': child_mo.reservation_state,
                'explosion_id': self.id,
            })

    def _create_po_items(self, source, level, po_items):
        for po_item in po_items:
            self.env['mrp.mto.supply.chain.line.po'].create({
                'product_id': po_item.product_id.id,
                'purchase_id': po_item.order_id.id,
                'level': level,
                'product_qty': po_item.product_uom_qty,
                'product_uom_id': po_item.product_uom.id,
                'po_state': po_item.state,
                'partner_id': po_item.order_id.partner_id.id,
                'date_planned': po_item.order_id.date_planned,
                'date_order': po_item.order_id.date_order,
                'source': source,
                'poitem_qty_received': po_item.qty_received,
                'explosion_id': self.id,
            })

    def mrp_mto_supply_chain_explosion(self):
        for sale in self.sale_id:
            level = 0
            delivery_date = sale.commitment_date or sale.expected_date
            # sale items
            for sale_item in sale.order_line:
                self.env['mrp.mto.supply.chain.line'].create({
                    'product_id': sale_item.product_id.id,
                    'level': level,
                    'product_qty': sale_item.product_uom_qty,
                    'product_uom_id': sale_item.product_uom.id,
                    'so_state': sale.state,
                    'date_order': sale.date_order,
                    'delivery_date': delivery_date,
                    'qty_delivered': sale_item.qty_delivered,
                    'qty_invoiced': sale_item.qty_invoiced,
                    'explosion_id': self.id,
                    'sale_line_id': sale_item.id,
                })
            level = 1
            # PO item di primo livello
            po_items = sale.order_line.purchase_line_ids
            self._create_po_items(self.sale_id.name, level, po_items)
            # MO di primo livello
            mos = sale.procurement_group_id.stock_move_ids.created_production_id.procurement_group_id.mrp_production_ids
            self._create_mos(self.sale_id.name, level, mos)
            while mos:
                level += 1
                for mo in mos:
                    # Child MOs
                    child_mos = mo.procurement_group_id.stock_move_ids.created_production_id.procurement_group_id.mrp_production_ids
                    self._create_mos(mo.name, level, child_mos)
                    # Child PO items
                    po_items_1 = mo.procurement_group_id.stock_move_ids.created_purchase_line_id
                    po_items_2 = mo.procurement_group_id.stock_move_ids.move_orig_ids.purchase_line_id
                    po_items = po_items_1 | po_items_2
                    self._create_po_items(mo.name, level, po_items)
                mos = mos.procurement_group_id.stock_move_ids.created_production_id.procurement_group_id.mrp_production_ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('MTO Supply Chain'),
            'auto_search': True,
            'res_model': 'mrp.mto.supply.chain',
            'target': 'new',
            'views': [(self.env.ref('mrp_mto_analytic.mrp_mto_supply_chain_form2').id, "form")],
            'res_id': self.id,
        }


class MrpMtoSupplyChainLine(models.TransientModel):
    _name = "mrp.mto.supply.chain.line"
    _description = 'MRP MTO Supply Chain Line Report'

    explosion_id = fields.Many2one('mrp.mto.supply.chain', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    level = fields.Integer('Level', readonly=True)
    product_qty = fields.Float('Requested Qty', readonly=True, digits='Product Unit of Measure')
    product_uom_id = fields.Many2one('uom.uom', 'UoM', readonly=True)
    qty_delivered = fields.Float('Delivered Qty', readonly=True, digits='Product Unit of Measure')
    qty_invoiced = fields.Float('Invoiced Qty', readonly=True, digits='Product Unit of Measure')
    date_order = fields.Datetime('Order Date', readonly=True)
    delivery_date = fields.Datetime('Planned Delivery Date', readonly=True)
    sale_line_id = fields.Many2one("sale.order.line", 'Sales Order Item', readonly=True)
    mto_indicator = fields.Boolean('MTO', readonly=True, compute="_get_mto_indicator")
    so_state = fields.Selection([
        ('draft', 'Quotation'),
        ('sent', 'Quotation Sent'),
        ('sale', 'Sales Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled'),], string='Status', readonly=True)

    @api.depends('sale_line_id')
    def _get_mto_indicator(self):
        for record in self:
            record.mto_indicator = record.sale_line_id._check_mto()
        return True


class MrpMtoSupplyChainLineMO(models.TransientModel):
    _name = "mrp.mto.supply.chain.line.mo"
    _description = 'MRP MTO Supply Chain Line Report MO'

    explosion_id = fields.Many2one('mrp.mto.supply.chain', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    manufacture_id = fields.Many2one('mrp.production', 'Manufacturing Order', readonly=True)
    level = fields.Integer('Level', readonly=True)
    product_qty = fields.Float('Requested Qty', readonly=True, digits='Product Unit of Measure')
    product_uom_id = fields.Many2one('uom.uom', 'UoM', readonly=True)
    qty_producing = fields.Float('Produced Qty', readonly=True, digits='Product Unit of Measure')
    source = fields.Char('Source Document', readonly=True)
    date_planned_start_pivot = fields.Datetime('Planned Start Pivot Date', readonly=True)
    date_planned_finished_pivot = fields.Datetime('Planned End Pivot Date', readonly=True)
    reservation_state = fields.Selection([
        ('confirmed', 'Waiting'),
        ('assigned', 'Ready'),
        ('waiting', 'Waiting Another Operation')], string='Material Availability', readonly=True)
    mo_state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('progress', 'In Progress'),
        ('to_close', 'To Close'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')], string='Status', readonly=True)


class MrpMtoSupplyChainLinePO(models.TransientModel):
    _name = "mrp.mto.supply.chain.line.po"
    _description = 'MRP MTO Supply Chain Line Report PO'

    explosion_id = fields.Many2one('mrp.mto.supply.chain', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    purchase_id = fields.Many2one('purchase.order', 'Purchase Order', readonly=True)
    level = fields.Integer('Level', readonly=True)
    product_qty = fields.Float('Requested Qty', readonly=True, digits='Product Unit of Measure')
    product_uom_id = fields.Many2one('uom.uom', 'UoM', readonly=True)
    po_state = fields.Selection([
        ('draft', 'RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')], string='Status', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Vendor', readonly=True)
    date_planned = fields.Datetime(string='Receipt Date', readonly=True)
    date_order = fields.Datetime(string='Order Date', readonly=True)
    poitem_qty_received = fields.Float('Received Qty', readonly=True, digits='Product Unit of Measure')
    source = fields.Char('Source Document', readonly=True)
