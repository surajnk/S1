# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # sale_stock mosale.order.linedule
    # propagate analytic account in MOs and POs
    def _prepare_procurement_values(self, group_id=False):
        values = super()._prepare_procurement_values(group_id)
        values.update({'account_analytic_id': self.order_id.analytic_account_id.id})
        return values

    # sale_purchase module
    # propagate analytic account in PO Service
    def _purchase_service_prepare_line_values(self, purchase_order, quantity=False):
        values = super()._purchase_service_prepare_line_values(purchase_order=purchase_order, quantity=quantity)
        values.update({'account_analytic_id': self.order_id.analytic_account_id.id})
        return values

    def _check_mto(self):
        check_mto = False
        for line in self:
            product_routes = line.route_id or (line.product_id.route_ids + line.product_id.categ_id.total_route_ids)
            wh_mto_route = line.order_id.warehouse_id.mto_pull_id.route_id
        if not wh_mto_route:
            try:
                wh_mto_route = self.env['stock.warehouse']._find_global_route('stock.route_warehouse0_mto', _('Make To Order'))
            except UserError:
                pass
        if wh_mto_route and wh_mto_route in product_routes:
            check_mto = True
        else:
            check_mto = False
        return check_mto

    def _check_buy(self):
        check_buy = False
        for line in self:
            product_routes = self.product_id.route_ids
            wh_buy_route = self.order_id.warehouse_id.buy_pull_id.route_id
        if not wh_buy_route:
            try:
                wh_buy_route = self.env['stock.warehouse']._find_global_route('stock.route_warehouse0_buy', _('Buy'))
            except UserError:
                pass
        if wh_buy_route and wh_buy_route in product_routes:
            check_buy = True
        else:
            check_buy = False
        return check_buy

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        self.button_create_analytic_account()
        super().action_confirm()
        buy_mto = False
        for order in self:
            # checks on sale order items
            if any(line._check_mto() for line in order.order_line):
                if any(line.product_id.type == 'consu' and line.price_unit != 0.0 and not line._check_mto() for line in order.order_line):
                    raise UserError(_("MTO Sales are not allowed for consumable products without MTO procurement, please set the price as zero"))
                if not order.analytic_account_id:
                    raise UserError(_("MTO Sale Order requires an Analytic Account"))
            # analytic account in delivery
            for line in order.order_line:
                if line.product_id.type == 'product':
                    buy_mto = line._check_mto() and line._check_buy()
                    if buy_mto:
                        continue
                    else:
                        line.move_ids.write({'analytic_account_id': order.analytic_account_id.id})
            # Child POs - days to purchase
            purchase_order_ids = order.order_line.purchase_line_ids.order_id.ids
            if purchase_order_ids:
                purchase_orders = self.env['purchase.order'].browse(purchase_order_ids)
                for purchase in purchase_orders:
                    days_to_purchase = order.company_id.days_to_purchase
                    purchase.date_order = purchase.date_order - relativedelta(days=days_to_purchase)
                    if order.warehouse_id.calendar_id and not days_to_purchase == 0:
                        calendar = order.warehouse_id.calendar_id
                        purchase.date_order = calendar.plan_hours(0.0, purchase.date_order, True)
                        purchase.date_order = calendar.plan_days(-days_to_purchase - 1, purchase.date_order, True)
            # Update Mo Quantity
            procurement_groups = self.env['procurement.group'].search([('sale_id', 'in', self.ids)])
            mrp_production_ids = set(procurement_groups.stock_move_ids.created_production_id.ids) | \
                                 set(procurement_groups.mrp_production_ids.ids)
            for mrp_rec in self.env['mrp.production'].browse(list(mrp_production_ids)):
                sale_line = order.order_line.filtered(lambda x: x.product_id.id == mrp_rec.product_id.id)
                if sale_line:
                    sale_line = sale_line[0]
                    if sale_line.x_order_customer_uom:
                        #mrp_rec.product_uom_id = sale_line.x_order_customer_uom.id
                        mrp_rec.x_order_master_yards = sale_line.x_order_master_yards
                        for wo in mrp_rec.workorder_ids:
                            embossing_val = self.env['product.embossing'].search([('name','=',wo.operation_id.name)],limit=1).id
                            wo.x_pattern_wo = embossing_val
                            wo.qty_output_wo = sale_line.x_order_master_yards
                            wo.x_mo_product_name = sale_line.product_id.name
                            wo.x_wo_delivery_date = order.commitment_date
        return True

    def button_create_analytic_account(self):
        for record in self:
            analytic_account = self.env['account.analytic.account'].create({
                    'name': record.name,
                    'partner_id': record.partner_id.id,
                })
            record.analytic_account_id = analytic_account.id

    def action_cancel(self):
        purchase_order_line_ids = self.env['purchase.order.line'].search([('sale_order_id', '=', self.id)]).filtered(lambda r: r.state not in ['done', 'cancel', 'purchase'])
        purchase_order_line_ids.unlink()
        return super().action_cancel()

    def action_view_analytic_lines(self):
        self.ensure_one()
        analytic_lines_ids = self.analytic_account_id.line_ids.ids
        view_id = self.env.ref('mrp_mto_analytic.view_account_analytic_line_sales_order_tree').id
        action = {
            'res_model': 'account.analytic.line',
            'type': 'ir.actions.act_window',
            'name': _("Analytic Lines by %s", self.name),
            'domain': [('id', 'in', analytic_lines_ids)],
            'views': [(view_id, "tree"),(False, "form"),(False, "graph"),(False, "pivot")],
        }
        return action
