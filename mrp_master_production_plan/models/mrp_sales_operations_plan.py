# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import time
from datetime import datetime, date, time, timedelta
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero, float_round, date_utils


class MrpSalesOperationsPlan(models.Model):
    _name = "mrp.sales.operations.plan"
    _description = "Sales and Operations Plan"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_planned'

    STATE_SELECTION = [
        ("begin", _("Begin")),
        ("end", _("End")),
        ("demand", _("Demand")),
        ("draft", _("Draft")),
        ("load", _("Rough Cut Capacity")),
        ("done", _("Released")),
        ("closed", _("Closed")),
        ("cancel", _("Cancelled"))]

    name = fields.Char('SOP Item Reference', required=True, index=True, copy=False, readonly=True, default='New')
    origin = fields.Many2one('mrp.planning.version', 'Version', readonly=True)
    pir_id = fields.Many2one('mrp.independent.requirements', 'PIR ID', readonly=True)
    qty_pir = fields.Float('PIR Qty', compute='_get_pir_qty', store=True, group_operator=False)
    active = fields.Boolean('Active', default=True, tracking=True)
    date_planned = fields.Datetime('Planned Date', required=True, readonly=True, states={'draft': [('readonly', False)]}) 
    state = fields.Selection(STATE_SELECTION, 'Status', index=True, required=True, copy=False, default='draft', readonly=True, tracking=True)
    product_id = fields.Many2one('product.product', "Product", check_company=True, domain=[('type', '=', 'product', )], readonly=True, required=True, states={'draft': [('readonly', False)]})
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', related='product_id.product_tmpl_id')
    product_qty = fields.Float("Planned Quantity", required=True, digits='Product Unit of Measure', readonly=True, states={'draft': [('readonly', False)]}, default=1.0, group_operator=False)
    product_uom_id = fields.Many2one('uom.uom', 'UoM', readonly=True, related='product_id.uom_id', store=True)
    bom_id = fields.Many2one('mrp.bom', "BoM", compute='_get_bom_subcontractor', store=True)
    bom_type = fields.Selection(string='BoM Type', store=True, related='bom_id.type')
    subcontractor_id = fields.Many2one('product.supplierinfo', 'Subcontractor', compute='_get_bom_subcontractor', store=True, readonly=True, states={'draft': [('readonly', False)]})
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', required=True, readonly=True, states={'draft': [('readonly', False)]}, domain="[('manufacture_to_resupply', '=', 'True')]")
    company_id = fields.Many2one('res.company', 'Company', readonly=True, related='warehouse_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', related='warehouse_id.company_id.currency_id')
    qty_on_hand = fields.Float('On hand Qty', compute='_get_on_hand_qty', store=True, group_operator=False)
    qty_cum_demand = fields.Float('Cum Demand Qty', compute='_get_cum_demand_qty', store=True, group_operator=False)
    qty_cum_requested = fields.Float('Cum Requested Qty', compute='_get_cum_moves_qty', store=True, group_operator=False)
    qty_cum_mo_draft = fields.Float('Cum draft MOs Qty', compute='_get_cum_draft_mo_qty', store=True, group_operator=False)
    qty_cum_posub_draft = fields.Float('Cum draft Sub POs Qty', compute='_get_cum_draft_posub_qty', store=True, group_operator=False)
    qty_cum_supply = fields.Float('Cum Supply Qty', compute='_get_cum_moves_qty', store=True, group_operator=False)
    qty_cum_planned = fields.Float('Cum Planned Qty', compute='_get_cum_planned_qty', store=True, group_operator=False)
    qty_inv_projected = fields.Float('Projected Stock Qty', compute='_get_inventory_proj_qty', store=True, group_operator=False)
    sops_revenues = fields.Float('SOP Revenues', digits='Product Price', compute='calculate_sops_amounts', store=True)
    sops_costs = fields.Float('SOP Costs', digits='Product Price', compute='calculate_sops_amounts', store=True)


    @api.depends('pir_id.product_qty')
    def _get_pir_qty(self):
        for record in self:
            record.qty_pir = record.pir_id.product_qty
        return True

    def _get_planning_parameters(self, product_id, warehouse_id):
        mpp_parameters = self.env['mrp.mpp.parameters'].search([('product_id', '=', product_id.id),('warehouse_id', '=', warehouse_id.id)], limit=1)
        return mpp_parameters

    @api.constrains('product_qty')
    def check_planned_quantity(self):
        if self.product_qty < 0.0:
            raise UserError(_('The planned quantity has to be positive!'))
        return True

    @api.depends('state', 'product_qty', 'qty_pir', 'product_id')
    def calculate_sops_amounts(self):
        sopsrevenues = 0.0
        sopscosts = 0.0
        for sop in self:
            if sop.state == 'demand':
                sopsrevenues = sop.product_id.product_tmpl_id.list_price * sop.qty_pir
            if sop.state in ('draft', 'load', 'done'):
                sopscosts = sop.product_id.standard_price * sop.product_qty
            sop.sops_revenues = sopsrevenues
            sop.sops_costs = sopscosts
        return True

    @api.model
    def _create_sequence(self, vals):
        if not vals.get('name') or vals.get('name') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('mrp.sales.operations.plan') or 'New'
        return vals
        
    @api.model
    def create(self, vals):
        vals = self._create_sequence(vals)
        res = super().create(vals)
        return res

    def button_load(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(_('Load is possible in Draft status only'))
        for record in self:
            if record.bom_id.type == 'subcontract' and not record.subcontractor_id:
                raise UserError(_('no subcontractor has been entered'))
            record.state = 'load'
            if record.bom_id.operation_ids and record.bom_id.type == 'normal':
                record.do_capacity_loading()
            else:
                record.button_done()
        return True
        
    def _get_date_planned_start(self):
        date_planned_start = False
        if not self.warehouse_id.calendar_id:
            raise UserError(_('no working calendar has been set at warehouse level'))
        if self.company_id.manufacturing_lead:
            date_planned_start = self.warehouse_id.calendar_id.plan_days(-self.company_id.manufacturing_lead -1, self.date_planned, True)
        else:
            date_planned_start = self.date_planned
        if self.product_id.produce_delay:
            date_planned_start = self.warehouse_id.calendar_id.plan_days(-self.product_id.produce_delay -1, date_planned_start, True)
        return date_planned_start
        
    def do_capacity_loading (self):
        date_planned_start = self._get_date_planned_start()
        for activity in self.bom_id.operation_ids:
            id_created= self.env['mrp.mpp.capacity'].create({
                'workcenter_id': activity.workcenter_id.id,
                'duration': activity.time_cycle_manual * self.product_qty / 60,
                #'capacity': activity.workcenter_id.wc_capacity,
                'product_id': self.product_id.id,
                'product_qty': self.product_qty,
                'product_uom_id': self.product_uom_id.id,
                'date_planned': date_planned_start,
                'SOP_item' : self.name,
                'sop_duration': activity.time_cycle_manual * self.product_qty / 60,
            })
        return True

    def button_done(self):
        if any(record.state != 'load' for record in self):
            raise UserError(_('Item release is possible in Rough Cut Capacity status only'))
        for record in self:
            record.state = 'done'
            id_created = self.env['mrp.production.plan'].create({
                'sop_id': record.id,
                'warehouse_id' : record.warehouse_id.id,
                'product_id' : record.product_id.id,
                'product_qty' : record.product_qty,
                'bom_id' : record.bom_id.id,
                'date_planned' : record.date_planned,
                'subcontractor_id' : record.subcontractor_id.id,
                'state' : 'draft'
            })
            id_created.button_load()
            if record.bom_id.type == 'normal':
                id_created.button_done()
        return True
        
    def button_cancel(self):
        if any(record.state not in ('begin','end','draft') for record in self):
            raise UserError(_('Item cancel is possible in draft, begin and end statuses only'))
        self.write({'state': 'cancel'})
        return True
        
    def button_reset(self):
        if any(record.state != 'load' for record in self):
            raise UserError(_('Reset is possible in load status only'))
        for record in self:
            mpp_cap_ids = self.env['mrp.mpp.capacity'].search([('SOP_item', '=', record.name)])
            for mpp_cap_id in mpp_cap_ids:
                mpp_cap_ids.unlink()
            record.write({'state': 'draft'})
        return True
        
    def button_close(self):
        self.write({'state': 'closed'})
        return True
        
    def unlink(self):
        res = super().unlink()
        if any(record.state not in ('cancel', 'closed') for record in self):
            raise UserError(_('only SOP items in cancel or closed status can be deleted'))
        return res

    @api.depends('product_id', 'warehouse_id')
    def _get_bom_subcontractor(self):
        for sop in self:
            if sop.product_id and sop.warehouse_id:
                mpp_parameters = self._get_planning_parameters(sop.product_id, sop.warehouse_id)
                if not mpp_parameters:
                    raise UserError(_('planning parameters record has not been created'))
                else:
                    sop.bom_id = mpp_parameters.bom_id.id
                    if sop.bom_id.type == 'subcontract':
                        sop.subcontractor_id = mpp_parameters.supplier_id.id
        return True

    @api.constrains('date_planned','warehouse_id')
    def _check_planned_date(self):
        for sop in self:
            if not sop.warehouse_id.calendar_id:
                raise UserError(_('no working calendar has been defined at warehouse level'))
            mpp_parameters = self._get_planning_parameters(sop.product_id, sop.warehouse_id)
            lt_days = mpp_parameters.total_lead_time
            today = datetime.now()
            min_planned_date = sop.warehouse_id.calendar_id.plan_days(lt_days, today, True)
            if (sop.date_planned < min_planned_date) and sop.state == 'draft':
                raise UserError(_('Please check Planned Date against to the Overall Throughput Time'))

    @api.depends('date_planned', 'product_id', 'product_qty', 'warehouse_id')
    def _get_on_hand_qty(self):
        for record in self:
            location = record.warehouse_id.lot_stock_id
            record.qty_on_hand = 0.0
            stock_quant_ids = self.env['stock.quant'].search([('product_id', '=', record.product_id.id),('location_id', 'child_of', location.id)])
            record.qty_on_hand = sum(stock_quant_ids.mapped('quantity'))

    @api.depends('date_planned', 'product_id', 'product_qty', 'warehouse_id')
    def _get_cum_moves_qty(self):
        for record in self:
            location = record.warehouse_id.lot_stock_id
            record.qty_cum_requested = 0.0
            record.qty_cum_supply = 0.0
            stock_moves = self.env['stock.move'].search([('product_id', '=', record.product_id.id),('date', '<=', record.date_planned),('state', 'not in', ['done','cancel', 'draft'])])
            locations = self.env['stock.location'].search([('id', 'child_of', location.id)])
            stock_moves_out = stock_moves.filtered(lambda r: (r.group_id.sale_id.id == False and r.location_id.id in locations.ids))
            stock_moves_in = stock_moves.filtered(lambda r: r.location_dest_id.id in locations.ids)
            record.qty_cum_requested = sum(stock_moves_out.mapped('product_uom_qty'))
            record.qty_cum_supply = sum(stock_moves_in.mapped('product_uom_qty'))
            
    @api.depends('date_planned', 'product_id', 'product_qty', 'warehouse_id')
    def _get_cum_demand_qty(self):
        for record in self:
            record.qty_cum_demand = 0.0
            pir_ids = self.env['mrp.independent.requirements'].search([('product_id', '=', record.product_id.id),('warehouse_id', '=', record.warehouse_id.id),('state', '=', 'done'),('date_planned', '<=', record.date_planned)])
            record.qty_cum_demand = sum(pir_ids.mapped('product_qty'))
    
    @api.depends('date_planned', 'product_id', 'product_qty', 'warehouse_id')
    def _get_cum_draft_mo_qty(self):
        for record in self:
            record.qty_cum_mo_draft = 0.0
            location = record.warehouse_id.lot_stock_id
            locations = self.env['stock.location'].search([('id', 'child_of', location.id)])
            draft_mo_ids = self.env['mrp.production'].search([('location_dest_id', 'in', locations.ids),('product_id', '=', record.product_id.id),('date_planned_start', '<=', record.date_planned),('state', '=', 'draft')])
            record.qty_cum_mo_draft = sum(draft_mo_ids.mapped('product_qty'))
            
    @api.depends('date_planned', 'product_id', 'product_qty', 'warehouse_id')
    def _get_cum_draft_posub_qty(self):
        for record in self:
            record.qty_cum_posub_draft = 0.0
            draft_posub_ids = self.env['purchase.order.line'].search([('order_id.picking_type_id.warehouse_id', '=', record.warehouse_id.id),('product_id', '=', record.product_id.id),('date_planned', '<=', record.date_planned),('state', 'in', ('draft','sent','to approve'))])
            record.qty_cum_posub_draft = sum(draft_posub_ids.mapped('product_qty'))
    
    @api.depends('date_planned', 'product_id', 'product_qty', 'warehouse_id')
    def _get_cum_planned_qty(self):
        for record in self:
            record.qty_cum_planned = 0.0
            sop_ids = self.env['mrp.sales.operations.plan'].search([('product_id', '=', record.product_id.id),('warehouse_id', '=', record.warehouse_id.id),('state', 'in', ['draft','load','done']),('date_planned', '<=', record.date_planned)])
            record.qty_cum_planned = sum(sop_ids.mapped('product_qty'))
    
    @api.depends('date_planned', 'product_id', 'product_qty', 'warehouse_id', 'state')
    def _get_inventory_proj_qty(self):
        for record in self:
            record.qty_inv_projected = record.qty_on_hand - record.qty_cum_demand - record.qty_cum_requested + record.qty_cum_supply +  record.qty_cum_planned + record.qty_cum_mo_draft + record.qty_cum_posub_draft
            
    def _get_lot_qty(self, qty_available):
        lot_qty = 0.0
        number_lots = 1
        for sop in self:
            mpp_parameters = self._get_planning_parameters(sop.product_id, sop.warehouse_id)
            #fixed lot
            if mpp_parameters.lot_qty_method == 'F':
                number_lots = int(qty_available // mpp_parameters.mpp_fixed_order_qty) + 1
                lot_qty = mpp_parameters.mpp_fixed_order_qty
            #lot for lot
            else:
                lot_qty = qty_available
            remainder = mpp_parameters.mpp_multiple_order_qty > 0 and lot_qty % mpp_parameters.mpp_multiple_order_qty or 0.0
            if float_compare(remainder, 0.0, precision_rounding=sop.product_uom_id.rounding) > 0:
                lot_qty += mpp_parameters.mpp_multiple_order_qty - remainder
        return lot_qty, number_lots
