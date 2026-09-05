# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime, date, timedelta
from odoo.exceptions import UserError


class MrpIndependentRequirements(models.Model):
    _name = "mrp.independent.requirements"
    _description = "Planned Independent Requirements"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_planned'

    STATE_SELECTION = [
        ("draft", _("Draft")),
        ("cancel", _("Cancelled")),
        ("done", _("Approved"))]

    @api.model
    def _get_source_warehouse(self):
        company_id = self.env.context.get('default_company_id', self.env.company)
        return company_id.supply_warehouse_id.id
        
    @api.model
    def _get_warehouse(self):
        company_id = self.env.context.get('default_company_id', self.env.company)
        return company_id.warehouse_id.id

    origin = fields.Many2one('mrp.planning.version', 'Version', required=True, domain=[('state', '=', 'open')],
        readonly=True, states={'draft': [('readonly', False)]}) 
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True, related='warehouse_id.company_id', store=True)
    currency_id = fields.Many2one('res.currency', 'Currency', related='warehouse_id.company_id.currency_id') 
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', default=_get_warehouse, required=True, readonly=True, states={'draft': [('readonly', False)]})
    supply_warehouse_id = fields.Many2one('stock.warehouse', 'Source Warehouse', default=_get_source_warehouse, required=True, readonly=True, states={'draft': [('readonly', False)]})
    user_id = fields.Many2one('res.users', 'Planning Responsible', related='origin.user_id', store=True)
    state = fields.Selection(STATE_SELECTION, 'Status', index=True, required=True, readonly=True, copy=False, default='draft')
    product_id = fields.Many2one("product.product", 'Product', required=True, check_company=True, domain=[('type', 'in', ['product', 'consu'])], readonly=True, states={'draft': [('readonly', False)]})
    uom_id = fields.Many2one('uom.uom', 'UoM', readonly=True, related='product_id.uom_id', store=True)
    product_qty = fields.Float("Planned Qty", required=True, digits='Product Unit of Measure', readonly=True, states={'draft': [('readonly', False)]}, default=1.0)
    date_planned = fields.Datetime('Planned Date', readonly=True, compute='_get_planned_date', store=True)
    date_requested = fields.Datetime('Requested Date', required=True, readonly=True, states={'draft': [('readonly', False)]}) 
    date_start = fields.Datetime('Version Start Date', required=True, related='origin.date_start')
    date_end = fields.Datetime("Version End Date", required=True, related='origin.date_end')
    pir_revenue = fields.Float('PIR Revenue', digits='Product Price', compute='calculate_pir_amounts', store=True)
    pir_cost = fields.Float('PIR Cost', digits='Product Price', compute='calculate_pir_amounts', store=True)
    stock_transfer_id = fields.Many2one('stock.transfer', 'Stock Transfer Document')
    stock_transfer_state = fields.Selection(string=_('Stock Transfer State'), related='stock_transfer_id.state')
    purchase_id = fields.Many2one('purchase.order', 'Purchase Order')
    purchase_state = fields.Selection(string='Purchase Order State', related='purchase_id.state')
    
    
    @api.constrains('warehouse_id')
    def check_working_calendar(self):
        if self.warehouse_id and not self.warehouse_id.calendar_id:
            raise UserError(_('no working calendar has been set on the warehouse: please check %s')% record.warehouse_id.name)
        return True
    
    @api.constrains('product_qty')
    def check_planned_quantity(self):
        if self.product_qty <= 0.0:
            raise UserError(_('The Requested Quantity has to be positive!'))
        return True
    
    def get_sop_integration(self, product_id, supply_warehouse_id):
        sop_ids = self.env['mrp.sales.operations.plan'].search([('product_id', '=', product_id.id),('state', 'not in', ('cancel', 'closed')),('warehouse_id', '=', supply_warehouse_id.id)])
        if len(sop_ids) == 0:
            id_created_begin = self.env['mrp.sales.operations.plan'].create({
                'warehouse_id' : supply_warehouse_id.id,
                'product_id' : product_id.id,
                'product_qty' : 0.0,
                'date_planned' : datetime.strptime('1900-01-01','%Y-%m-%d'),
                'state' : 'begin'
            })
            id_created_end = self.env['mrp.sales.operations.plan'].create({
                'warehouse_id' : supply_warehouse_id.id,
                'product_id' : product_id.id,
                'product_qty' : 0.0,
                'date_planned' : datetime.strptime('2999-12-31','%Y-%m-%d'),
                'state' : 'end'
            })
        self.product_id.sop_active = True
        return True
        
    def get_sop_demand(self, product_id, supply_warehouse_id, origin, date_planned):
        id_demand = self.env['mrp.sales.operations.plan'].create({
            'origin': origin.id,
            'pir_id': self.id,
            'warehouse_id' : supply_warehouse_id.id,
            'product_id' : product_id.id,
            'product_qty' : 0.0,
            'date_planned' : date_planned,
            'state' : 'demand'
        })
        self.product_id.sop_active = True
        return True
    
    def button_done(self):
        for record in self:
            #if not record.supply_warehouse_id:
            #    raise UserError(_('no supply warehouse has been entered'))
            mpp_parameters = record._get_planning_parameters(record.supply_warehouse_id)
            if record.warehouse_id != record.supply_warehouse_id:
                if mpp_parameters:
                    ddi_id = self.env['mrp.distribution.deployment'].create({
                            'warehouse_id': record.warehouse_id.id,
                            'supply_warehouse_id': record.supply_warehouse_id.id,
                            'product_id': record.product_id.id,
                            'product_qty': record.product_qty,
                            'date_planned': record.date_planned,
                            'pir_id': record.id,
                            'state' : 'draft'
                        })
                    record.get_sop_integration(record.product_id, record.supply_warehouse_id)
            elif record.warehouse_id == record.supply_warehouse_id:
                if not mpp_parameters:
                    dpi_id = self.env['mrp.distribution.procurement'].create({
                            'warehouse_id': record.supply_warehouse_id.id,
                            'product_id': record.product_id.id,
                            'product_qty': record.product_qty,
                            'date_planned': record.date_planned,
                            'pir_id': record.id,
                            'state' : 'draft'
                        })
                else:
                    record.get_sop_integration(record.product_id, record.supply_warehouse_id)
                    record.get_sop_demand(record.product_id, record.supply_warehouse_id, record.origin, record.date_planned)
            record.write({'state': 'done'})
        return True

    def check_buy_product(self, product_id, supply_warehouse_id):
        check_buy = product_id.purchase_ok
        mpp_parameters = self._get_planning_parameters(supply_warehouse_id)
        if not mpp_parameters:
            if not check_buy:
                raise UserError(_('Product %s is not a purchased one')% product_id.name)
            else:
                supplier = self.env['product.supplierinfo'].search([('product_tmpl_id','=', product_id.product_tmpl_id.id),('is_subcontractor','=', False)], limit=1)
                if not supplier:
                    raise UserError(_('Product %s does not have a supplier')% product_id.name)
        return True

    @api.constrains('product_id', 'warehouse_id', 'supply_warehouse_id')
    def check_distribution_item(self):
        for record in self:
            mpp_parameters = self._get_planning_parameters(record.supply_warehouse_id)
            # warehouse planning
            if record.warehouse_id == record.supply_warehouse_id:
                record.check_buy_product(record.product_id, record.supply_warehouse_id)
            # distribution planning
            elif record.supply_warehouse_id and record.warehouse_id != record.supply_warehouse_id:
                if record.product_id.type == 'consu' or (record.product_id.type == 'product' and not mpp_parameters):
                    raise UserError(_('for internal procurement storable products with MPP parameters are allowed only: please check %s')% record.product_id.name)
        return True
        
    def button_draft(self):
        if any(record.state != 'done' for record in self):
            raise UserError(_('Reset is possible in approved status only'))
        for record in self:
            # Purchase Orders
            if record.purchase_id and record.purchase_id.state in ('purchase','done'):
                raise UserError(_('Reset is not possible: POs already confirmed, Please cancel them before!'))
            elif record.purchase_id and record.purchase_id.state not in ('purchase','done'):
                record.purchase_id.button_cancel()
                pir_ids = self.env['mrp.independent.requirements'].search([('purchase_id', '=', record.purchase_id.id)])
                pir_ids.purchase_id = False
                pir_ids.state = 'draft'
                dpi_ids = self.env['mrp.distribution.procurement'].search([('pir_id', 'in', pir_ids.ids)])
                dpi_ids.state = 'cancel'
            else:
                dpi_id = self.env['mrp.distribution.procurement'].search([('pir_id', '=', record.id)])
                dpi_id.state = 'cancel'
            # Stock Transfer Documents
            if record.stock_transfer_id and record.stock_transfer_id.state not in ('draft', 'cancel', 'confirm'):
                raise UserError(_('Reset is not possible: Transfer Documents already in progress or closed!'))
            elif record.stock_transfer_id and record.stock_transfer_id.state in ('draft', 'cancel', 'confirm'):
                record.stock_transfer_id.button_draft()
                record.stock_transfer_id.button_cancel()
                pir_ids = self.env['mrp.independent.requirements'].search([('stock_transfer_id', '=', record.stock_transfer_id.id)])
                pir_ids.stock_transfer_id = False
                pir_ids.state = 'draft'
                ddi_ids = self.env['mrp.distribution.deployment'].search([('pir_id', 'in', pir_ids.ids)])
                ddi_ids.state = 'cancel'
            else:
                ddi_id = self.env['mrp.distribution.deployment'].search([('pir_id', '=', record.id)])
                ddi_id.state = 'cancel'
            # Sales and Operations Planning
            sop_ids = self.env['mrp.sales.operations.plan'].search([('pir_id', '=', record.id)])
            sop_ids.state = 'cancel'
            active_pirs = self.env['mrp.independent.requirements'].search([('product_id', '=', record.product_id.id), ('warehouse_id', '=', record.supply_warehouse_id.id), ('state', '=', 'done')])
            if not active_pirs:
                record.product_id.sop_active = False
            # status updating
            record.write({'state': 'draft'})
        return True
        
    def button_cancel(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(_('Cancel is possible in draft status only'))
        self.write({'state': 'cancel'})
        return True
        
    def unlink(self):
        res = super().unlink()
        if any(record.state != 'cancel' for record in self):
            raise UserError(_('Deletion is possible in cancel status only'))
        return res
        
    def _get_planning_parameters(self, warehouse_id):
        for pir in self:
            mpp_parameters = self.env['mrp.mpp.parameters'].search([('product_id', '=', pir.product_id.id),('warehouse_id', '=', warehouse_id.id)], limit=1)
        return mpp_parameters
        
    @api.depends('product_id', 'date_requested', 'supply_warehouse_id', 'warehouse_id')
    def _get_planned_date(self):
        date_planned = False
        for pir in self:
            if pir.date_requested and pir.warehouse_id and pir.warehouse_id.calendar_id:
                date_planned = pir.warehouse_id.calendar_id.plan_days(- pir.product_id.sale_delay, pir.date_requested, True)
                if pir.supply_warehouse_id and pir.warehouse_id == pir.supply_warehouse_id:
                    mpp_parameters = pir._get_planning_parameters(pir.warehouse_id)
                    if mpp_parameters:
                        date_planned = pir.warehouse_id.calendar_id.plan_days(- mpp_parameters.sales_lead_time, pir.date_requested, True)
                pir.date_planned = date_planned
        return True

    @api.constrains('date_planned','supply_warehouse_id','origin')
    def _check_planned_date(self):
        for pir in self:
            if pir.supply_warehouse_id and not pir.supply_warehouse_id.calendar_id:
                raise UserError(_('no working calendar has been defined at warehouse level for the source warehouse'))
            if pir.date_planned:
                if (pir.date_planned < pir.origin.date_start) or (pir.date_planned > pir.origin.date_end):
                    raise UserError(_('Planned Date is not within the Validity Period'))
                if pir.supply_warehouse_id:
                    mpp_parameters = pir._get_planning_parameters(pir.supply_warehouse_id)
                    lt_days = mpp_parameters.total_lead_time
                    min_planned_date = pir.supply_warehouse_id.calendar_id.plan_days(lt_days, pir.origin.date_start, True)
                    if pir.date_planned < min_planned_date:
                        raise UserError(_('Please check Planned Date against to the Overall Throughput Time'))
        return True 
        
    @api.constrains('date_planned', 'product_id', 'warehouse_id', 'origin')
    def _check_same_planned_date(self):
        for record in self:
            pir_ids = self.env['mrp.independent.requirements'].search([
                ('origin', '=', record.origin.id),
                ('product_id', '=', record.product_id.id),
                ('warehouse_id', '=', record.warehouse_id.id),
                ('date_planned', '=', record.date_planned),
                ('state', '!=', 'cancel'),
            ])
            if len(pir_ids) > 1:
                raise UserError(_('Another PIR exists in the same planned date'))
        return True

    @api.depends('product_id','product_qty')
    def calculate_pir_amounts(self):
        revenue = 0.0
        cost = 0.0
        for pir in self:
            revenue = pir.product_id.product_tmpl_id.list_price * pir.product_qty
            cost = pir.product_id.product_tmpl_id.standard_price * pir.product_qty
        pir.pir_revenue = revenue
        pir.pir_cost = cost
        return True
