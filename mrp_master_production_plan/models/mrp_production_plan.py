# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
import time
from datetime import datetime, date, time, timedelta
from odoo.exceptions import UserError


class MrpMasterProductionPlan(models.Model):
    _name = "mrp.production.plan"
    _description = "Master Production Plan"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'product_id, date_planned'

    STATE_SELECTION = [
        ("draft", _("Draft")),
        ("load", _("Capacity Check")),
        ("done", _("Approved")),
        ("cancel", _("Cancelled"))]
    
    name = fields.Char('MPP Item Reference', required=True, index=True, copy=False, readonly=True, default='New')
    sop_id = fields.Many2one('mrp.sales.operations.plan', 'SOP Item Reference', readonly=True)
    sop_item = fields.Boolean('SOP Item',compute='_get_sop_item', store=True)
    changeable = fields.Boolean('Changeable Item', compute='_get_changeable_item', store=True)
    active = fields.Boolean(default=True)
    state = fields.Selection(STATE_SELECTION, 'Status', index=True, required=True, readonly=True, copy=False, default='draft')
    date_planned = fields.Datetime('Planned Date', required=True)
    product_id = fields.Many2one('product.product', "Product", check_company=True, domain=[('type', '=', 'product')], required=True)
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', related='product_id.product_tmpl_id')
    product_qty = fields.Float("Planned Quantity", required=True, digits='Product Unit of Measure', default=1.0)
    product_uom_id = fields.Many2one('uom.uom', 'UoM', related='product_id.uom_id', store=True)
    bom_id = fields.Many2one('mrp.bom', "BoM", compute='_get_bom_subcontractor', store=True)
    bom_type = fields.Selection(string='BoM Type', store=True, related='bom_id.type')
    subcontractor_id = fields.Many2one('product.supplierinfo', 'Subcontractor', compute='_get_bom_subcontractor', store=True, readonly=True, states={'draft': [('readonly', False)]})
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', required=True, domain="[('manufacture_to_resupply', '=', 'True')]")
    company_id = fields.Many2one('res.company', 'Company', readonly=True, related='warehouse_id.company_id', store=True)
    user_id = fields.Many2one('res.users', 'Planning Responsible', required=True, tracking=True, default=lambda self: self.env.user, check_company=True)
    mpp_cost = fields.Float('MPP Costs', digits='Product Price', compute='calculate_mpp_amount', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', related='warehouse_id.company_id.currency_id')

    @api.constrains('product_qty')
    def check_planned_quantity(self):
        if self.product_qty <= 0.0:
            raise UserError(_('The planned quantity has to be positive!'))
        return True
        
    def _get_planning_parameters(self, product_id, warehouse_id):
        mpp_parameters = self.env['mrp.mpp.parameters'].search([('product_id', '=', product_id.id),('warehouse_id', '=', warehouse_id.id)], limit=1)
        return mpp_parameters
    
    @api.depends('product_id', 'warehouse_id')
    def _get_bom_subcontractor(self):
        for mpp in self:
            if mpp.product_id and mpp.warehouse_id:
                mpp_parameters = self._get_planning_parameters(mpp.product_id, mpp.warehouse_id)
                if not mpp_parameters:
                    raise UserError(_('planning parameters record has not been created'))
                else:
                    mpp.bom_id = mpp_parameters.bom_id.id
                    if mpp.bom_id.type == 'subcontract' and not mpp.subcontractor_id:
                        mpp.subcontractor_id = mpp_parameters.supplier_id.id
        return True
    
    @api.model
    def _create_sequence(self, vals):
        if not vals.get('name') or vals.get('name') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('mrp.production.plan') or 'New'
        return vals
        
    @api.model
    def create(self, vals):
        vals = self._create_sequence(vals)
        res = super().create(vals)
        return res

    def unlink(self):
        res = super().unlink()
        if any(record.state not in ('cancel', 'done') for record in self):
            raise UserError(_('Deletion is possible in cancel or done status only'))
        for mpp in self:
            mo = self.env['mrp.production'].search([('origin', '=', mpp.name),('state', '!=', 'cancel')], limit=1)
            po = self.env['purchase.order'].search([('origin', '=', mpp.name),('state', '!=', 'cancel')], limit=1)
            if mo or po:
                raise UserError(_('linked MOs or POs still active, please delete/cancel them before'))
        return res

    @api.constrains('date_planned','warehouse_id')
    def _check_planned_date(self):
        for mpp in self:
            if mpp.warehouse_id and not mpp.warehouse_id.calendar_id:
                raise UserError(_('no working calendar has been defined at warehouse level'))
            mpp_parameters = self._get_planning_parameters(mpp.product_id, mpp.warehouse_id)
            lt_days = mpp_parameters.total_lead_time
            today = datetime.now()
            min_planned_date = self.warehouse_id.calendar_id.plan_days(lt_days, today, True)
            if (mpp.date_planned < min_planned_date) and mpp.state == 'draft':
                raise UserError(_('Please check Planned Date against to the Overall Throughput Time'))
        return True

    def button_cancel(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(_('Cancel is possible in status draft only'))
        for record in self:
            if record.sop_item:
                sop_cap_ids = self.env['mrp.mpp.capacity'].search([('SOP_item', '=', record.sop_id.name)])
                sop_cap_ids.unlink()
            record.state = 'cancel'
            record.sop_id.state = 'cancel'
        return True
        
    def button_reset(self):
        if any(record.state != 'load' for record in self):
            raise UserError(_('Reset is possible in load status only'))
        for record in self:
            mpp_cap_ids = self.env['mrp.mpp.capacity'].search([('MPP_item', '=', record.name)])
            for mpp_cap_id in mpp_cap_ids:
                mpp_cap_ids.unlink()
            record.state = 'draft'
            if record.sop_item:
                if record.bom_id.operation_ids and record.bom_id.type == 'normal':
                    record.sop_id.do_capacity_loading()
        return True
        
    def button_load(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(_('Load is possible in draft status only'))
        for record in self:
            record.state = 'load'
            if record.bom_id.type == 'subcontract' and not record.subcontractor_id:
                raise UserError(_('no subcontractor has been entered'))
            if record.bom_id.operation_ids and record.bom_id.type == 'normal':
                record.do_capacity_loading()
                # sop capacity reset
                if record.sop_item:
                    mpp_cap_ids = self.env['mrp.mpp.capacity'].search([('SOP_item', '=', record.sop_id.name)])
                    for mpp_cap_id in mpp_cap_ids:
                        mpp_cap_ids.unlink()
            else:
                record.button_done()
        return True
        
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
                'MPP_item' : self.name
            })
        return True
        
    def button_done(self):
        if any(record.state != 'load' for record in self):
            raise UserError(_('Approval is possible in load status only'))
        for record in self:
            if record.bom_id and record.bom_id.type == 'normal':
                record.action_manufacturing_order_create()
            elif record.bom_id and record.bom_id.type == 'subcontract':
                record.action_purchase_order_create()
            record.state = 'done'
            record.sop_id.state = 'closed'
        return True

    def _get_date_order(self):
        date_order = False
        for mpp in self:
            days_to_purchase = mpp.company_id.days_to_purchase
            subcontractor_delay = mpp.subcontractor_id.delay
            purchase_lead_time = subcontractor_delay + days_to_purchase
            date_order = mpp.date_planned - timedelta(days=purchase_lead_time)
            if mpp.warehouse_id.calendar_id and not days_to_purchase == 0:
                calendar = mpp.warehouse_id.calendar_id
                date_order = mpp.date_planned - timedelta(days=subcontractor_delay)
                date_order = calendar.plan_days(-days_to_purchase - 1, date_order, True)
        return date_order

    def action_purchase_order_create(self):
        self.ensure_one()
        date_order = self._get_date_order()
        id_purchase_order = self.env['purchase.order'].create({
            'partner_id': self.subcontractor_id.name.id,
            'currency_id': self.currency_id.id,
            'company_id': self.company_id.id,
            'origin': self.name,
            'date_order': date_order,
            'user_id': self.user_id.id,
            'picking_type_id': self.warehouse_id.in_type_id.id,
        })
        id_purchase_order_item = self.env['purchase.order.line'].create({
            'order_id': id_purchase_order.id,
            'date_planned': self.date_planned,
            'product_id': self.product_id.id,
            'name': self.product_id.name,
            'product_uom': self.product_uom_id.id,
            'product_qty': self.product_qty,
            'price_unit': self.subcontractor_id.price,
            'mpp_id': self.id,
        })
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

    def _prepare_manufacturing_order(self):
        self.ensure_one()
        location = self.env['stock.warehouse'].search([('id', '=', self.warehouse_id.id)], limit=1).lot_stock_id
        picking_type_id = self.env['stock.picking.type'].search([('code', '=', 'mrp_operation'), ('company_id', '=', self.company_id.id)], limit=1)
        location_src_id = picking_type_id.default_location_src_id.id or location.id
        location_dest_id = picking_type_id.default_location_dest_id.id or location.id
        date_planned_start = self._get_date_planned_start()
        return {
            'product_id': self.product_id.id,
            'bom_id': self.bom_id.id,
            'product_qty': self.product_qty,
            'product_uom_id': self.product_uom_id.id,
            'origin': self.name,
            'location_src_id': location_src_id,
            'location_dest_id': location_dest_id,
            'picking_type_id': picking_type_id.id,
            'date_planned_start': date_planned_start,
            'date_planned_start_pivot': date_planned_start,
            'date_planned_finished_pivot': self.date_planned,
            'company_id': self.company_id.id,
            'mpp_id': self.id,
        } 
    
    def action_manufacturing_order_create(self):
        self.ensure_one()
        vals = self._prepare_manufacturing_order()
        mo = self.env['mrp.production'].create(vals)
        mo.procurement_group_id = self.env['procurement.group'].create({'name': mo.name}).id
        #consumption moves
        moves_raw_values = mo._get_moves_raw_values()
        list_move_raw = []
        for move_raw_value in moves_raw_values:
            list_move_raw += [(0,_,move_raw_value)]
        mo.move_raw_ids = list_move_raw
        #finished products moves
        move_finished_values = mo._get_moves_finished_values()
        list_move_finished = []
        for move_finished_value in move_finished_values:
            list_move_finished += [(0,_,move_finished_value)]
        mo.move_finished_ids = list_move_finished
        #
        (mo.move_raw_ids | mo.move_finished_ids).write({
            'group_id': mo.procurement_group_id.id,
            'origin': mo.name
        })
        # workorders
        mo._create_workorder()
        return True
        
    @api.depends('product_id','product_qty')
    def calculate_mpp_amount(self):
        mppamount = 0.0
        for mpp in self:
            mppamount = mpp.product_id.standard_price * mpp.product_qty
        mpp.mpp_cost = mppamount
        return True
    
    @api.depends('sop_id')
    def _get_sop_item(self):
        for record in self:
            record.sop_item = False
            if record.sop_id:
                record.sop_item = True
        return True
        
    @api.depends('sop_id','state')
    def _get_changeable_item(self):
        for record in self:
            record.changeable = False
            if record.state == 'draft' and not record.sop_id:
                record.changeable = True
        return True
