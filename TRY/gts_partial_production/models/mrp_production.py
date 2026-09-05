# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round
from odoo.tools.safe_eval import safe_eval


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    partial_qty_produced = fields.Boolean(default=False)
    all_qty_produced = fields.Boolean(compute="_compute_all_qty_produced")

    def _compute_all_qty_produced(self):
        for prod in self:
            prod.all_qty_produced = prod.product_qty == prod.qty_produced

    def open_produce_product(self):
        """
        Function to check if workorders are generated and open produce wizard
        :return:
        """
        self.ensure_one()
        if not self.workorder_ids:
            raise UserError(_('Please create workorders first!'))
        action = self.env.ref('gts_partial_production.act_mrp_product_produce').read()[0]
        action_context = safe_eval(action.get('context', '{}'))
        context = dict(self.env.context)
        context.update(action_context)
        context.update({
            'active_id': self.id,
            'active_model': 'mrp.production',
            'default_production_id': self.id,
        })
        action['context'] = context
        return action

    # def _workorders_create(self, bom, bom_data):
    #     """
    #     :param bom: in case of recursive boms: we could create work orders for child
    #                 BoMs
    #     Overriden for not creating  lines in moves from workorder
    #     """
    #     workorders = self.env['mrp.workorder']
    #     bom_qty = bom_data['qty']
    #
    #     # Initial qty producing
    #     if self.product_id.tracking == 'serial':
    #         quantity = 1.0
    #     else:
    #         quantity = self.product_qty - sum(self.move_finished_ids.mapped('quantity_done'))
    #         quantity = quantity if (quantity > 0) else 0
    #
    #     for operation in bom.routing_id.operation_ids:
    #         # create workorder
    #         cycle_number = float_round(bom_qty / operation.workcenter_id.capacity,
    #                                    precision_digits=0, rounding_method='UP')
    #         duration_expected = (operation.workcenter_id.time_start +
    #                              operation.workcenter_id.time_stop +
    #                              cycle_number * operation.time_cycle * 100.0 / operation.workcenter_id.time_efficiency)
    #         workorder = workorders.create({
    #             'name': operation.name,
    #             'production_id': self.id,
    #             'workcenter_id': operation.workcenter_id.id,
    #             'operation_id': operation.id,
    #             'duration_expected': duration_expected,
    #             'state': len(workorders) == 0 and 'ready' or 'pending',
    #             'qty_producing': quantity,
    #             'capacity': operation.workcenter_id.capacity,
    #         })
    #         if workorders:
    #             workorders[-1].next_work_order_id = workorder.id
    #         workorders += workorder
    #
    #         # assign moves; last operation receive all unassigned moves (which case ?)
    #         moves_raw = self.move_raw_ids.filtered(lambda move: move.operation_id == operation)
    #         if len(workorders) == len(bom.routing_id.operation_ids):
    #             moves_raw |= self.move_raw_ids.filtered(lambda move: not move.operation_id)
    #         moves_finished = self.move_finished_ids.filtered(lambda move: move.operation_id == operation)
    #         # TODO: code does nothing, unless maybe by_products?
    #         moves_raw.mapped('move_line_ids').write({'workorder_id': workorder.id})
    #         (moves_finished + moves_raw).write({'workorder_id': workorder.id})
    #
    #         # workorder._generate_lot_ids()
    #     return workorders

    def post_inventory(self, cancel_backorder=False):
        for order in self:
            moves_not_to_do = order.move_raw_ids.filtered(lambda x: x.state == 'done')
            moves_to_do = order.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            for move in moves_to_do.filtered(lambda m: m.product_qty == 0.0 and m.quantity_done > 0):
                move.product_uom_qty = move.quantity_done
            # MRP do not merge move, catch the result of _action_done in order
            # to get extra moves.
            moves_to_do = moves_to_do._action_done()
            moves_to_do = order.move_raw_ids.filtered(lambda x: x.state == 'done') - moves_not_to_do

            finish_moves = order.move_finished_ids.filtered(lambda m: m.product_id == order.product_id and m.state not in ('done', 'cancel'))
            # the finish move can already be completed by the workorder.
            for move in finish_moves:
                if not move.quantity_done:
                    move.quantity_done = float_round(order.qty_producing - order.qty_produced, precision_rounding=order.product_uom_id.rounding, rounding_method='HALF-UP')
                    move.move_line_ids.lot_id = order.lot_producing_id
            order._cal_price(moves_to_do)

            moves_to_finish = order.move_finished_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            moves_to_finish = moves_to_finish._action_done(cancel_backorder=cancel_backorder)
            order.action_assign()
            consume_move_lines = moves_to_do.mapped('move_line_ids')
            order.move_finished_ids.move_line_ids.consume_line_ids = [(6, 0, consume_move_lines.ids)]
            order.partial_qty_produced = True
        return True
