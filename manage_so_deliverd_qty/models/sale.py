from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare, float_round


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # Override the default method to pass required master yard qty in the picking and move line
    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """
        Launch procurement group run method with required/custom fields genrated by a
        sale order line. procurement group will launch '_run_pull', '_run_buy' or '_run_manufacture'
        depending on the sale order line product rule.
        """
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        procurements = []
        for line in self:
            line = line.with_company(line.company_id)
            if line.state != 'sale' or not line.product_id.type in ('consu','product'):
                continue
            qty = line._get_qty_procurement(previous_product_uom_qty)
            if float_compare(qty, line.product_uom_qty, precision_digits=precision) >= 0:
                continue

            group_id = line._get_procurement_group()
            if not group_id:
                group_id = self.env['procurement.group'].create(line._prepare_procurement_group_vals())
                line.order_id.procurement_group_id = group_id
            else:
                # In case the procurement group is already created and the order was
                # cancelled, we need to update certain values of the group.
                updated_vals = {}
                if group_id.partner_id != line.order_id.partner_shipping_id:
                    updated_vals.update({'partner_id': line.order_id.partner_shipping_id.id})
                if group_id.move_type != line.order_id.picking_policy:
                    updated_vals.update({'move_type': line.order_id.picking_policy})
                if updated_vals:
                    group_id.write(updated_vals)

            values = line._prepare_procurement_values(group_id=group_id)
            product_qty = line.product_uom_qty - qty

            line_uom = line.product_uom
            quant_uom = line.product_id.uom_id
            product_qty, procurement_uom = line_uom._adjust_uom_quantities(product_qty, quant_uom)
            # Added code:  Note: Pass the required master yard qty in the picking and move line
            procurements.append(self.env['procurement.group'].Procurement(
                line.product_id, line.x_order_master_yards or product_qty, procurement_uom,
                line.order_id.partner_shipping_id.property_stock_customer,
                line.product_id.display_name, line.order_id.name, line.order_id.company_id, values))
        if procurements:
            self.env['procurement.group'].run(procurements)
        orders = list(set(x.order_id for x in self))
        for order in orders:
            reassign = order.picking_ids.filtered(
                lambda x: x.state == 'confirmed' or (x.state in ['waiting', 'assigned'] and not x.printed))
            if reassign:
                # Trigger the Scheduler for Pickings
                reassign.action_confirm()
                reassign.action_assign()
        return True

    # Update the qty_delivered in sale order line from stock move
    @api.depends('qty_delivered_method', 'qty_delivered_manual', 'analytic_line_ids.so_line', 'analytic_line_ids.unit_amount', 'analytic_line_ids.product_uom_id')
    def _compute_qty_delivered(self):
        super(SaleOrderLine, self)._compute_qty_delivered()
        for order_line in self:
            moves = order_line.move_ids.filtered(lambda x: x.picking_code == 'outgoing')
            if moves and moves[0].cust_qty and order_line.x_order_master_yards:
                order_line.qty_delivered = moves and moves[0].cust_qty