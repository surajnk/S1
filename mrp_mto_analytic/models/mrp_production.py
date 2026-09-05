# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from datetime import datetime
from odoo.tools import float_is_zero, float_round
import logging
from collections import defaultdict
import pytz

_logger = logging.getLogger(__name__)

class MrpOrderMessage(models.Model):
    _name="mrp.order.message"

    x_mrp_special_message =  fields.Char('Message')
    x_special_message_mrp_order_line = fields.Many2one('mrp.production')

class ProductionOrder(models.Model):
    _inherit = 'mrp.production'

    origin = fields.Char(readonly=True)
    x_order_master_yards = fields.Integer('Required Master Yards')
    x_order_customer_mrp_qty = fields.Char('Cust Qty',readonly=True)
    x_order_customer_mrp_width = fields.Char('Cust Wid',readonly=True)
    x_order_customer_mrp_length = fields.Char('Cust Len',readonly=True)
    x_order_customer_uom = fields.Char('Cust UoM')
    x_order_line_customer_mrp_qty = fields.Float('Cust Qty',digits='EF Product')
    x_order_line_customer_mrp_width = fields.Float('Cust Wid',digits='EF Product')
    x_order_line_customer_mrp_length = fields.Float('Cust Len',digits='EF Product')
    x_order_line_trim_width =  fields.Float('Trim Width')
    x_order_line_trim_length =  fields.Float('Trim length')
    x_order_line_machine_length = fields.Integer('Machine Length')
    x_order_mrp_over = fields.Char('Over %')
    x_order_mrp_under = fields.Char('Under %')
    x_mrp_order_slit = fields.Boolean('Multiple Slit Sizes')
    x_mrp_order_multi_slit_size = fields.One2many('mrp.multi.size','x_order_mrp_size_ref','Multi Slit Sizes')
    x_mrp_messages = fields.One2many('mrp.order.message','x_special_message_mrp_order_line','Special Messages')
    x_so_delivery_date = fields.Date("Requested Date")
    # x_mrp_confirmed_date = fields.Date(string='Confirmed Date')
    x_mrp_confirmed_date_boolean = fields.Boolean(string='Confirmed')
    x_mrp_confirmed_date_notify_boolean = fields.Boolean(string='Notify')
    week_year = fields.Char(string='Estimated Start Week')
    x_mrp_customer_msg = fields.Text(string='Customer Special Messages')
    workorder_week_field_ids = fields.One2many('workorder.week.field','workorder_week_prod','Workorder Info')
    x_mrp_order_comments = fields.Text(string='Order Comments')
    x_customer_name = fields.Many2one('res.partner',string='Customer')

    def _action_cancel(self):
        documents_by_production = {}
        for production in self:
            documents = defaultdict(list)
            for move_raw_id in self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
                iterate_key = self._get_document_iterate_key(move_raw_id)
                if iterate_key:
                    document = self.env['stock.picking']._log_activity_get_documents({move_raw_id: (move_raw_id.product_uom_qty, 0)}, iterate_key, 'UP')
                    for key, value in document.items():
                        documents[key] += [value]
            if documents:
                documents_by_production[production] = documents
            # log an activity on Parent MO if child MO is cancelled.
            finish_moves = production.move_finished_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            if finish_moves:
                production._log_downside_manufactured_quantity({finish_move: (production.product_uom_qty, 0.0) for finish_move in finish_moves}, cancel=True)

        self.workorder_ids.filtered(lambda x: x.state not in ['done', 'cancel']).action_cancel()
        finish_moves = self.move_finished_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
        raw_moves = self.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel'))

        for move in (finish_moves | raw_moves):
            move._action_cancel()

        picking_ids = self.picking_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
        picking_ids.action_cancel()

        for production, documents in documents_by_production.items():
            filtered_documents = {}
            for (parent, responsible), rendering_context in documents.items():
                if not parent or parent._name == 'stock.picking' and parent.state == 'cancel' or parent == production:
                    continue
                filtered_documents[(parent, responsible)] = rendering_context
            production._log_manufacture_exception(filtered_documents, cancel=True)

        # In case of a flexible BOM, we don't know from the state of the moves if the MO should
        # remain in progress or done. Indeed, if all moves are done/cancel but the quantity produced
        # is lower than expected, it might mean:
        # - we have used all components but we still want to produce the quantity expected
        # - we have used all components and we won't be able to produce the last units
        #
        # However, if the user clicks on 'Cancel', it is expected that the MO is either done or
        # canceled. If the MO is still in progress at this point, it means that the move raws
        # are either all done or a mix of done / canceled => the MO should be done.
        self.filtered(lambda p: p.state not in ['done', 'cancel'] and p.bom_id.consumption == 'flexible').write({'state': 'done'})

        return True

    @api.onchange('x_mrp_confirmed_date')
    def onchange_x_mrp_confirmed_date(self):
        for production in self:
            sale_order = production._get_related_sale_order()
            sale_order_line = production._get_related_sale_order_line(sale_order)
            if production.x_mrp_confirmed_date:
                production.write({'x_mrp_confirmed_date_boolean': True, 'x_mrp_confirmed_date_notify_boolean': True})
                sale_order_line.write({'x_mrp_line_revised_ship_date': production.x_mrp_confirmed_date})
                # Update workorder.x_confirmed_date
                for workorder in production.workorder_ids:
                    workorder.x_confirmed_date = production.x_mrp_confirmed_date
            if not production.x_mrp_confirmed_date:
                production.write({'x_mrp_confirmed_date_boolean': False, 'x_mrp_confirmed_date_notify_boolean': False})
                sale_order_line.write({'x_mrp_line_revised_ship_date': ''})
                # Clear workorder.x_confirmed_date
                for workorder in production.workorder_ids:
                    workorder.x_confirmed_date = False

    @api.onchange('x_mrp_confirmed_date_notify_boolean')
    def _onchange_x_mrp_confirmed_date_notify_boolean(self):
        if self.x_mrp_confirmed_date_notify_boolean:
            self.create_sale_order_activity()

    def create_sale_order_activity(self):
        for production in self:
            sale_order = production._get_related_sale_order()
            sale_order_line = production._get_related_sale_order_line(sale_order)
            if sale_order_line:
                sale_order = sale_order_line.order_id
                activity_type = self.env.ref('mail.mail_activity_data_todo').id  # Example activity type
                summary = 'MRP Confirmed Date Notification'
                note = 'The MRP Confirmed Date has been set.'
                self.env['mail.activity'].create({
                    'res_id': sale_order.id,
                    'res_model_id': self.env['ir.model'].search([('model', '=', 'sale.order')], limit=1).id,
                    'activity_type_id': activity_type,
                    'user_id': sale_order.create_uid.id,
                    'summary': summary,
                    'note': note,
                })

    def _get_children(self):
        self.ensure_one()
        procurement_moves = self.procurement_group_id.stock_move_ids
        child_moves = procurement_moves.move_orig_ids
        return (procurement_moves | child_moves).created_production_id.procurement_group_id.mrp_production_ids - self

    def _get_related_sale_order(self):
        self.ensure_one()
        sale_orders = self.move_dest_ids.mapped('sale_line_id.order_id')
        if sale_orders:
            return sale_orders[:1]
        fallback_sales = self.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
        return fallback_sales[:1]

    def _get_related_sale_order_line(self, sale_order=False):
        self.ensure_one()
        sale_lines = self.move_dest_ids.mapped('sale_line_id')
        if not sale_lines and sale_order:
            sale_lines = sale_order.order_line.filtered(lambda line: line.product_id == self.product_id)
        return sale_lines[:1]

    def action_confirm(self):
        res1=[(5,0,0)]
        res2=[(5,0,0)]
        interval_time = 0
        for production in self:
            # Update Row Material Quantity with req master yds if the uom is yds
            # after production
            #-----------------------------------------
            sale_order = production._get_related_sale_order()
            operation_ids = self.env['mrp.routing.workcenter']
            sale_order_line = production._get_related_sale_order_line(sale_order)
            if sale_order:
                production.x_mrp_order_slit = sale_order.x_is_multi_slit
                # production.x_so_delivery_date = sale_order.commitment_date
                if sale_order.commitment_date:
                    user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                    production.x_so_delivery_date = pytz.utc.localize(sale_order.commitment_date).astimezone(user_tz).date()
                else:
                    production.x_so_delivery_date = False
                production.x_mrp_customer_msg = sale_order.x_order_customer_msg
                production.x_customer_name = sale_order.partner_id.id
                for workorder in production.workorder_ids:
                    workorder.x_customer_name = sale_order.partner_id.id
            else:
                stock_order_partner = self.env['res.partner'].search(
                    [('name', '=', 'STOCK ORDER')], limit=1
                )
                production.x_customer_name = stock_order_partner.id
            if sale_order_line:
                for qc in sale_order_line.x_order_multi_slit_size_order_line:
                    val = {
                    'x_order_mrp_outs': qc.x_order_outs,
                    'x_order_mrp_size': qc.x_order_size,
                    'x_total_mrp_size': qc.x_total_size,
                    }
                    res1.append((0,0,val))
                production.x_mrp_order_multi_slit_size = res1
                production.x_order_master_yards = sale_order_line.x_order_master_yards
                # Update putup also
                production.put_up_rolls = sale_order_line.put_up_rolls
                production.uom_put_up = sale_order_line.uom_put_up
                production.x_put_up_rolls = sale_order_line.put_up_rolls
                production.x_uom_put_up = sale_order_line.uom_put_up
                production.outs = sale_order_line.outs
                production.put_up_size = sale_order_line.put_up_size
                production.put_up_uom_name = sale_order_line.x_order_customer_uom.name
                production.x_put_up_uom_name = sale_order_line.x_order_customer_uom.name
                production.addtnl_put_ups = sale_order_line.additional_put_ups
                production.x_order_customer_mrp_qty = str(sale_order_line.product_uom_qty) + ' ' + sale_order_line.x_order_customer_uom.name
                production.x_order_customer_mrp_width = sale_order_line.x_customer_order_width
                production.x_order_customer_mrp_length = sale_order_line.x_customer_order_length
                production.x_order_line_customer_mrp_qty = sale_order_line.product_uom_qty
                production.x_order_line_customer_mrp_length = sale_order_line.x_customer_order_length
                production.x_order_line_customer_mrp_width = sale_order_line.x_customer_order_width
                production.x_order_line_trim_width = sale_order_line.x_product_order_trim_width
                production.x_order_line_trim_length = sale_order_line.x_product_order_trim_length
                production.x_order_line_machine_length = sale_order_line.x_order_machine_length
                production.x_order_mrp_over = sale_order_line.x_order_line_tol_over
                production.x_order_mrp_under = sale_order_line.x_order_line_tol_under
                production.x_mrp_order_comments = sale_order_line.x_order_line_comments
                production.x_mrp_order_slit = sale_order_line.x_is_multi_slit_order_line
                if sale_order_line.x_is_multi_slit_order_line:
                    production.x_dynamic_putup = False
                    production.outs = 1
                else:
                    production.x_dynamic_putup = True
                # production.x_mrp_order_multi_slit_size = sale_order.x_order_multi_slit_size
                #production.x_order_customer_uom = sale_order_line.x_order_customer_uom.name
                if sale_order_line.x_order_customer_uom.name == 'shts':
                    #production.skip_split = True
                    production.put_up_rolls = 1
                    production.outs = 1
                    production.uom_put_up = 1
                for qc in sale_order_line.x_sale_line_customer_message:
                    val = {
                    'x_mrp_special_message': qc.x_sale_special_message
                    }
                    res2.append((0,0,val))
                production.x_mrp_messages = res2
                for mv_rec in production.move_raw_ids:
                    if mv_rec.product_uom and mv_rec.product_uom.name == 'yds':
                        mv_rec.product_uom_qty = sale_order_line.x_order_master_yards
            else:
                for mv_rec in production.move_raw_ids:
                    if mv_rec.product_uom and mv_rec.product_uom.name == 'yds':
                        mv_rec.product_uom_qty = production.x_order_master_yards
            floating_times_id = self.env['mrp.floating.times'].search([('warehouse_id', '=', production.picking_type_id.warehouse_id.id)])
            floating_times_id_new = self.env['mrp.floating.times'].search([('warehouse_id', '=', production.picking_type_id.warehouse_id.id)])
            if (production.x_order_master_yards > 0 and production.x_order_master_yards <= 10000):
                interval_time = (floating_times_id_new.mrp_operations_first * 60)
            if (production.x_order_master_yards > 10000 and production.x_order_master_yards <= 25000):
                interval_time = (floating_times_id_new.mrp_operations_second * 60)
            if (production.x_order_master_yards > 25000 and production.x_order_master_yards <= 50000):
                interval_time = (floating_times_id_new.mrp_operations_third * 60)
            if (production.x_order_master_yards > 50000 and production.x_order_master_yards <= 100000):
                interval_time = (floating_times_id_new.mrp_operations_fourth * 60)
            if (production.x_order_master_yards > 100000):
                interval_time = (floating_times_id_new.mrp_operations_fifth * 60)
            if not floating_times_id:
                raise UserError(_('Floating Times record has not been created yet for the warehouse: %s')% production.picking_type_id.warehouse_id.name)
            warehouse_calendar = production.picking_type_id.warehouse_id.calendar_id
            
            # if production.x_so_delivery_date:
            #     start_date = datetime.combine(production.x_so_delivery_date, datetime.min.time())
            start_date = datetime.now()
            if production.x_so_delivery_date:
                start_date = datetime.combine(production.x_so_delivery_date, datetime.min.time())

            #_logger.info("STARTTT DTTEEEEE '%s'",start_date)
            # workorders scheduling
            duration_expected = sum(production.workorder_ids.mapped('duration_expected'))
            workorder_count = len(production.workorder_ids)
            
            # Compute the total interval time to subtract
            total_interval_time = timedelta(minutes=duration_expected + (interval_time * (workorder_count - 1)))
            
            # Subtract the total interval time from the start_date
            start_date -= total_interval_time
            start_date_week = start_date.strftime("%Y-%W")
            production.week_year = start_date_week
            workorder_weeks = []
            for workorder in production.workorder_ids:
                workorder.x_confirmed_date = production.x_mrp_confirmed_date
                workorder.date_planned_start_wo = start_date
                calendar = workorder.workcenter_id.resource_calendar_id if workorder.workcenter_id else None
                if not workorder.prev_work_order_id:
                    #_logger.info("WTHN IF NOTT CONFIRM")
                    #_logger.info("WOO DTTEEEEE '%s'",workorder.date_planned_start_wo)
                    # calendar = workorder.workcenter_id.resource_calendar_id
                    if calendar:
                        workorder.date_planned_start_wo = calendar.plan_hours(0.0, workorder.date_planned_start_wo, True)
                        #_logger.info("WOO DTTEEEEE IFFFFF NOTTTT'%s'",workorder.date_planned_start_wo)
                else:
                    # _logger.info("WTHN ELSEE CONFIRM")
                    if workorder.prev_work_order_id:
                        # _logger.info("WOO DTTEEEEE ELSEEE BAAAAA'%s'",workorder.date_planned_start_wo)
                        workorder.date_planned_start_wo = calendar.plan_hours(0.0, workorder.date_planned_start_wo, True)
                        # _logger.info("WOO DTTEEEEE ELSEEE'%s'",workorder.date_planned_start_wo)

                #_logger.info("WOO DTTEEEEE '%s'",workorder.date_planned_start_wo)
                end_date = start_date + timedelta(minutes=workorder.duration_expected)
                workorder_week = workorder.date_planned_start_wo.strftime("%Y-%W") if workorder.date_planned_start_wo else ''
                #_logger.info("WEEEKKKKKK '%s'",workorder_week)
                workorder_weeks.append((workorder.operation_id.name, workorder_week))
                workorder.date_planned_start_wo = False
                start_date = end_date + timedelta(minutes=interval_time)

            production.write({'workorder_week_field_ids': [(0, 0, {'operation_name': op_name, 'week_year': week_year}) for op_name, week_year in workorder_weeks]})
        super().action_confirm()
        date = False
        for production in self:
            # Child MOs - propagate analytic account
            child_mos_ids = production.procurement_group_id.stock_move_ids.created_production_id.procurement_group_id.mrp_production_ids.ids
            if child_mos_ids:
                child_mos = self.env['mrp.production'].browse(child_mos_ids).filtered(lambda r: r.state in ['draft', 'confirmed'])
                child_mos.write({'analytic_account_id': production.analytic_account_id.id})
            # Child POs - days to purchase
            po1 = production.procurement_group_id.stock_move_ids.created_purchase_line_id.order_id
            po2 = production.procurement_group_id.stock_move_ids.move_orig_ids.purchase_line_id.order_id
            purchase_orders = po1 | po2
            for purchase in purchase_orders:
                days_to_purchase = production.company_id.days_to_purchase
                purchase.date_order = purchase.date_order - relativedelta(days=days_to_purchase)
                if production.picking_type_id.warehouse_id.calendar_id and not days_to_purchase == 0:
                    calendar = production.picking_type_id.warehouse_id.calendar_id
                    purchase.date_order = calendar.plan_hours(0.0, purchase.date_order, True)
                    purchase.date_order = calendar.plan_days(-days_to_purchase - 1, purchase.date_order, True)
            for wo in production.workorder_ids:
                wo.qty_output_wo = production.x_order_master_yards
                operation_ids |= wo.operation_id
                for mv_rec in production.move_raw_ids:
                    mv_rec.x_listed_operations = operation_ids

            child_mo = production._get_children()
            if child_mo:
                master_yards = 0
                sale_order = production._get_related_sale_order()
                sale_order_line = production._get_related_sale_order_line(sale_order)
                if sale_order_line:
                    master_yards = sale_order_line.x_order_master_yards
                else:
                    master_yards = production.x_order_master_yards
                for ch_mo in child_mo:
                    ch_mo.write({'x_order_master_yards': master_yards})
                    for c_mv_rec in ch_mo.move_raw_ids:
                        if c_mv_rec.product_uom and c_mv_rec.product_uom.name == 'yds':
                            c_mv_rec.product_uom_qty = master_yards
                    for c_wo in ch_mo.workorder_ids:
                        c_wo.qty_output_wo = master_yards
        return True

    def button_mark_done(self):
        for production in self:
            production.move_raw_ids.write({'analytic_account_id': production.analytic_account_id.id})
            production.move_finished_ids.write({'analytic_account_id': production.analytic_account_id.id})
        return super().button_mark_done()

    def write(self, vals):
        if not self._context.get('update_analytic'):
            for production in self:
                if 'analytic_account_id' in vals and production.state not in ('done','cancel'):
                    moves = (production.mapped('move_raw_ids') + production.mapped('move_finished_ids')).filtered(lambda r: r.state not in ['done', 'cancel'])
                    for mv in moves:
                        if not mv.analytic_account_id:
                            mv.write({'analytic_account_id': vals['analytic_account_id']})
                    child_mo_ids = production.procurement_group_id.stock_move_ids.created_production_id.procurement_group_id.mrp_production_ids.ids
                    production_order_ids = self.env['mrp.production'].browse(child_mo_ids).filtered(lambda r: r.state in ('draft','confirmed'))
                    for production in production_order_ids:
                        if not production.analytic_account_id:
                            production.with_context({'update_analytic': True}).write({'analytic_account_id': production.analytic_account_id.id})
        res = super().write(vals)
        return res

    def action_remove_confirmation(self):
        for production in self:
            sale_order = production._get_related_sale_order()
            sale_order_line = production._get_related_sale_order_line(sale_order)
            production.write({'x_mrp_confirmed_date_boolean': False,'x_mrp_confirmed_date':'','x_mrp_confirmed_date_notify_boolean': False})
            sale_order_line.write({'x_mrp_line_revised_ship_date': ''})

    @api.onchange('x_mrp_confirmed_date')
    def onchange_x_mrp_confirmed_date(self):
        for production in self:
            sale_order = production._get_related_sale_order()
            sale_order_line = production._get_related_sale_order_line(sale_order)
            if production.x_mrp_confirmed_date:
                production.write({'x_mrp_confirmed_date_boolean': True,'x_mrp_confirmed_date_notify_boolean': True})
                sale_order_line.write({'x_mrp_line_revised_ship_date': production.x_mrp_confirmed_date})
            if not production.x_mrp_confirmed_date:
                production.write({'x_mrp_confirmed_date_boolean': False,'x_mrp_confirmed_date_notify_boolean': False})
                sale_order_line.write({'x_mrp_line_revised_ship_date': ''})



class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    x_order_customer_mrp_wo_qty = fields.Char('Cust Qty',related="production_id.x_order_customer_mrp_qty",readonly=True)
    x_order_customer_mrp_wo_width = fields.Char('Cust Wid',related="production_id.x_order_customer_mrp_width",readonly=True)
    x_order_customer_mrp_wo_length = fields.Char('Cust Len',related="production_id.x_order_customer_mrp_length",readonly=True)

    def action_wip(self):
        for order in self:
            order.write({'state': 'progress'})

class ChangeProductionQty(models.TransientModel):
    _inherit = 'change.production.qty'

    def change_prod_qty(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for wizard in self:
            production = wizard.mo_id
            produced = sum(production.move_finished_ids.filtered(lambda m: m.product_id == production.product_id).mapped('quantity_done'))
            if wizard.product_qty < produced:
                format_qty = '%.{precision}f'.format(precision=precision)
                raise UserError(_(
                    "You have already processed %(quantity)s. Please input a quantity higher than %(minimum)s ",
                    quantity=format_qty % produced,
                    minimum=format_qty % produced
                ))
            old_production_qty = production.product_qty
            new_production_qty = wizard.product_qty
            done_moves = production.move_finished_ids.filtered(lambda x: x.state == 'done' and x.product_id == production.product_id)
            qty_produced = production.product_id.uom_id._compute_quantity(sum(done_moves.mapped('product_qty')), production.product_uom_id)

            factor = (new_production_qty - qty_produced) / (old_production_qty - qty_produced)
            update_info = production._update_raw_moves(factor)
            documents = {}
            for move, old_qty, new_qty in update_info:
                iterate_key = production._get_document_iterate_key(move)
                if iterate_key:
                    document = self.env['stock.picking']._log_activity_get_documents({move: (new_qty, old_qty)}, iterate_key, 'UP')
                    for key, value in document.items():
                        if documents.get(key):
                            documents[key] += [value]
                        else:
                            documents[key] = [value]
            production._log_manufacture_exception(documents)
            finished_moves_modification = self._update_finished_moves(production, new_production_qty - qty_produced, old_production_qty - qty_produced)
            if finished_moves_modification:
                production._log_downside_manufactured_quantity(finished_moves_modification)
            production.write({'product_qty': new_production_qty})

            for wo in production.workorder_ids:
                operation = wo.operation_id
                wo.duration_expected = wo._get_duration_expected(ratio=new_production_qty / old_production_qty)
                wo.qty_output_wo = production.product_qty
                quantity = wo.qty_production - wo.qty_produced
                if production.product_id.tracking == 'serial':
                    quantity = 1.0 if not float_is_zero(quantity, precision_digits=precision) else 0.0
                else:
                    quantity = quantity if (quantity > 0 and not float_is_zero(quantity, precision_digits=precision)) else 0
                wo._update_qty_producing(quantity)
                if wo.qty_produced < wo.qty_production and wo.state == 'done':
                    wo.state = 'progress'
                if wo.qty_produced == wo.qty_production and wo.state == 'progress':
                    wo.state = 'done'
                    if wo.next_work_order_id.state == 'pending':
                        wo.next_work_order_id.state = 'ready'
                # assign moves; last operation receive all unassigned moves
                # TODO: following could be put in a function as it is similar as code in _workorders_create
                # TODO: only needed when creating new moves
                moves_raw = production.move_raw_ids.filtered(lambda move: move.operation_id == operation and move.state not in ('done', 'cancel'))
                moves_raw_uom = production.move_raw_ids.filtered(lambda move: move.product_uom.name=="yds")
                for mwr in moves_raw_uom:
                    mwr.product_uom_qty = production.product_qty
                if wo == production.workorder_ids[-1]:
                    moves_raw |= production.move_raw_ids.filtered(lambda move: not move.operation_id)
                moves_finished = production.move_finished_ids.filtered(lambda move: move.operation_id == operation) #TODO: code does nothing, unless maybe by_products?
                moves_raw.mapped('move_line_ids').write({'workorder_id': wo.id,})
                (moves_finished + moves_raw).write({'workorder_id': wo.id})
        return {}

class MrpMultiSize(models.Model):
    _name = "mrp.multi.size"

    x_order_mrp_outs = fields.Integer('Outs',digits='EF Price')
    x_order_mrp_size = fields.Float('Size',digits='EF Price')
    x_total_mrp_size = fields.Float('Total Size',digits='EF Price')
    x_order_mrp_size_ref = fields.Many2one('mrp.production',"Slit sizes")


class WorkorderWeekField(models.Model):
    _name= "workorder.week.field"

    operation_name = fields.Char('Operation')
    week_year = fields.Char('Week')
    workorder_week_prod = fields.Many2one('mrp.production','Production')
