# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, date, time, timedelta
from odoo.tools import float_compare, float_is_zero, float_round, date_utils
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import logging
from odoo import SUPERUSER_ID

_logger = logging.getLogger(__name__)


class MrpSopPlanningWizard(models.TransientModel):
    _name = "mrp.sop.massive.planning.wizard"
    _description = "SOP Massive Planning"


    product_ids = fields.Many2many('product.product', string='Products', domain="[('sop_active','!=',False)]")
    all_products = fields.Boolean('All Products')
    sop_item_ids = fields.Many2many('mrp.sales.operations.plan', string='Sales & Operations Planning Items')
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', required=True, domain="[('manufacture_to_resupply', '=', 'True')]")


    def get_planning(self):
        if not self.product_ids and not self.all_products:
            raise UserError(_('select a product at least or set All Products indicator'))
        if self.product_ids and self.all_products:
            raise UserError(_('select a products or set All Products indicator'))
        if self.all_products:
            products = self.env['product.product'].search([('sop_active','!=',False)])
            mpp_parameters_ids = self.env['mrp.mpp.parameters'].search([('product_id', 'in', products.ids),('warehouse_id', '=', self.warehouse_id.id)])
            for mpp_parameters_id in mpp_parameters_ids:
                self._sop_planning(mpp_parameters_id.product_id, mpp_parameters_id.warehouse_id)
        else:
            mpp_parameters_ids = self.env['mrp.mpp.parameters'].search([('product_id', 'in', self.product_ids.ids),('warehouse_id', '=', self.warehouse_id.id)])
            for mpp_parameters_id in mpp_parameters_ids:
                self._sop_planning(mpp_parameters_id.product_id, mpp_parameters_id.warehouse_id)
        return True

    def _sop_planning(self, product_id, warehouse_id):
        qty_available = 0.0
        sop_draft_items = self.env['mrp.sales.operations.plan'].search([
            ('state', '=', 'draft'),
            ('product_id', '=', product_id.id),
            ('warehouse_id', '=', warehouse_id.id),
            ])
        sop_draft_items.button_cancel()
        self._action_update_all_qty(product_id, warehouse_id)
        sop_demand_items = self.env['mrp.sales.operations.plan'].search([
            ('state', '=', 'demand'),
            ('product_id', '=', product_id.id),
            ('warehouse_id', '=', warehouse_id.id),
            ])
        for sop_demand_item in sop_demand_items:
            try:
                date_planned_sop = False
                date_planned_st = False
                mpp_parameters = sop_demand_item._get_planning_parameters(product_id, warehouse_id)
                bom_id = sop_demand_item.bom_id
                subcontractor_id = sop_demand_item.subcontractor_id
                # safety stock
                qty_available = sop_demand_item.qty_inv_projected - mpp_parameters.mpp_minimum_stock_qty
                # date planned
                if sop_demand_item.date_planned < datetime.now():
                    date_planned_sop = datetime.now()
                else:
                    date_planned_sop = sop_demand_item.date_planned
                # safety time
                safety_time = - mpp_parameters.mpp_safety_time
                date_planned_st = warehouse_id.calendar_id.plan_days(safety_time, date_planned_sop, True)
                if qty_available < 0.0:
                    # coverage days lot method
                    if mpp_parameters.lot_qty_method == 'S':
                        last_date = warehouse_id.calendar_id.plan_days(mpp_parameters.mpp_coverage_days, date_planned_sop, True)
                        domain_date = [('date_planned', '>=', date_planned_sop.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('date_planned', '<=', last_date.strftime(DEFAULT_SERVER_DATETIME_FORMAT))]
                        demand_records = sop_demand_items.filtered_domain(domain_date)
                        qty_available = min(demand_records.mapped('qty_inv_projected')) - mpp_parameters.mpp_minimum_stock_qty
                    lot_qty, number_lots = sop_demand_item._get_lot_qty(abs(qty_available))
                    if number_lots > sop_demand_item.company_id.number_maximum_lots:
                        raise UserError(_('please check lot quantity'))
                    if bom_id.type == 'normal':
                        for i in range(number_lots):
                            mpp_id = self.env['mrp.sales.operations.plan'].create({
                                'warehouse_id' : warehouse_id.id,
                                'product_id' : product_id.id,
                                'product_qty' : lot_qty,
                                'date_planned' : date_planned_st,
                                'bom_id' : bom_id.id,
                                'state' : 'draft',
                            })
                    elif bom_id.type == 'subcontract':
                        for i in range(number_lots):
                            mpp_id = self.env['mrp.sales.operations.plan'].create({
                                'warehouse_id' : warehouse_id.id,
                                'product_id' : product_id.id,
                                'product_qty' : lot_qty,
                                'date_planned' : date_planned_st,
                                'bom_id' : bom_id.id,
                                'state' : 'draft',
                                'subcontractor_id' : subcontractor_id.id,
                            })
                self._action_update_projected_qty(product_id, warehouse_id)
            except UserError as error:
                if error:
                    _logger.error(error.args[0])
                    model_id = self.env['ir.model'].search([('model', '=', 'mrp.independent.requirements')]).id
                    activity = self.env['mail.activity'].search([('res_id', '=', sop_demand_item.pir_id.id), ('res_model_id', '=', model_id), ('note', '=', error.args[0])])
                    if not activity:
                        sop_demand_item.pir_id.activity_schedule('mail.mail_activity_data_warning', note=error.args[0], user_id=sop_demand_item.pir_id.user_id.id or SUPERUSER_ID,)
        return True

    def _action_update_projected_qty(self, product_id, warehouse_id):
        sop_ids = self.env['mrp.sales.operations.plan'].search([('product_id', '=', product_id.id),('warehouse_id', '=', warehouse_id.id)])
        for sop_id in sop_ids:
            sop_id.qty_cum_planned = 0.0
            sop_id.qty_inv_projected = 0.0
            domain_cum_planned = [('state', 'in', ['draft','load','done']),('date_planned', '<=', sop_id.date_planned)]
            sop_planned_ids = sop_ids.filtered_domain(domain_cum_planned)
            for sop_planned_id in sop_planned_ids:
                sop_id.qty_cum_planned += sop_planned_id.product_qty
            sop_id.qty_inv_projected = sop_id.qty_on_hand - sop_id.qty_cum_demand - sop_id.qty_cum_requested + sop_id.qty_cum_supply + sop_id.qty_cum_planned + sop_id.qty_cum_mo_draft + sop_id.qty_cum_posub_draft
        return True

    def _action_update_all_qty(self, product_id, warehouse_id):
        sop_ids = self.env['mrp.sales.operations.plan'].search([('product_id', '=', product_id.id),('warehouse_id', '=', warehouse_id.id)])
        location = warehouse_id.lot_stock_id
        locations = self.env['stock.location'].search([('id', 'child_of', location.id)])
        for sop_id in sop_ids:
            sop_id.qty_on_hand = 0.0
            sop_id.qty_cum_demand = 0.0
            sop_id.qty_cum_requested = 0.0
            sop_id.qty_cum_supply = 0.0
            sop_id.qty_cum_mo_draft = 0.0
            sop_id.qty_cum_posub_draft = 0.0
            sop_id.qty_cum_planned = 0.0
            sop_id.qty_inv_projected = 0.0
            #1 on_hand_qty
            stock_quant_ids = self.env['stock.quant'].search([('product_id', '=', sop_id.product_id.id),('location_id', 'in',  locations.ids)])
            sop_id.qty_on_hand = sum(stock_quant_ids.mapped('quantity'))
            #2 qty_cum_demand
            pir_ids = self.env['mrp.independent.requirements'].search([('product_id', '=', sop_id.product_id.id),('warehouse_id', '=', sop_id.warehouse_id.id),('state', '=', 'done'),('date_planned', '<=', sop_id.date_planned)])
            sop_id.qty_cum_demand = sum(pir_ids.mapped('product_qty'))
            #3 qty_cum_requested and cum_supply_qty
            stock_moves = self.env['stock.move'].search([('product_id', '=', sop_id.product_id.id),('date', '<=', sop_id.date_planned),('state', 'not in', ['done','cancel', 'draft'])])
            stock_moves_out = stock_moves.filtered(lambda r: (r.group_id.sale_id.id == False and r.location_id.id in locations.ids))
            stock_moves_in = stock_moves.filtered(lambda r: r.location_dest_id.id in locations.ids)
            sop_id.qty_cum_requested = sum(stock_moves_out.mapped('product_uom_qty'))
            sop_id.qty_cum_supply = sum(stock_moves_in.mapped('product_uom_qty'))
            #4 cum_draft_mo_qty
            draft_mo_ids = self.env['mrp.production'].search([('location_dest_id', 'in', locations.ids),('product_id', '=', sop_id.product_id.id),('date_planned_start', '<=', sop_id.date_planned),('state', '=', 'draft')])
            sop_id.qty_cum_mo_draft = sum(draft_mo_ids.mapped('product_qty'))
            #5 cum_draft_posub_qty
            draft_subpo_ids = self.env['purchase.order.line'].search([('order_id.picking_type_id.warehouse_id', '=', sop_id.warehouse_id.id),('product_id', '=', sop_id.product_id.id),('date_planned', '<=', sop_id.date_planned),('state', 'in', ('draft','sent','to approve'))])
            sop_id.qty_cum_posub_draft = sum(draft_subpo_ids.mapped('product_qty'))
            #6 cum_planned_qty
            domain_cum_planned = [('state', 'in', ['draft','load','done']),('date_planned', '<=', sop_id.date_planned)]
            sop_planned_ids = sop_ids.filtered_domain(domain_cum_planned)
            sop_id.qty_cum_planned = sum(sop_planned_ids.mapped('product_qty'))
            # inv_proj_qty
            sop_id.qty_inv_projected = sop_id.qty_on_hand - sop_id.qty_cum_demand - sop_id.qty_cum_requested + sop_id.qty_cum_supply + sop_id.qty_cum_planned + sop_id.qty_cum_mo_draft + sop_id.qty_cum_posub_draft
        return True
