# Copyright 2021 Alfredo de la fuente - AvanzOSC
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import models, fields, api, exceptions, _


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    capacity = fields.Float(
        string='Yards Per Hour', default=1.0)
    time_start = fields.Float(
        string='Time before prod.', help="Time in minutes for the setup.")
    time_stop = fields.Float(
        string='Clean-up Time.', help="Time in minutes for the cleaning.")
    routing_wc_product_line_ids = fields.One2many(
        'mrp.routing.wc.product.line', 'mrp_routing_workcenter_id', 'Product Details')
    routing_operation_interval_ids = fields.One2many(
        'mrp.routing.wc.interval', 'mrp_routing_interval_id', 'Operation Interval Details')
    operation_products_ids = fields.Many2many(
        'product.product', 'rel_operation_components', 'wo_id', 'product_id', string='Components Use in Operation')
    occupied = fields.Boolean('Blocked')    

    @api.depends('time_cycle_manual', 'time_mode', 'workorder_ids')
    def _compute_time_cycle(self):
        result = super(MrpRoutingWorkcenter, self)._compute_time_cycle()
        manual_ops = self.filtered(
            lambda operation: operation.time_mode == 'manual')
        for operation in manual_ops:
            operation.time_cycle = operation.time_cycle_manual
        operations = self - manual_ops
        for operation in operations.filtered(lambda x: x.capacity):
            data = self.env['mrp.workorder'].read_group(
                [('operation_id', '=', operation.id),
                 ('qty_produced', '>', 0),
                 ('state', '=', 'done')
                 ],
                ['operation_id', 'duration', 'qty_produced'],
                ['operation_id'], limit=operation.time_mode_batch)
            count_data = dict(
                (item['operation_id'][0],
                 (item['duration'],
                  item['qty_produced'])) for item in data)
            if count_data.get(operation.id) and count_data[operation.id][1]:
                operation.time_cycle = (
                    count_data[operation.id][0] /
                    count_data[operation.id][1]) * (operation.capacity or 1.0)
            else:
                operation.time_cycle = operation.time_cycle_manual
        return result

    @api.constrains('capacity')
    def _check_capacity(self):
        if any(routing_workcenter.capacity < 0.0
               for routing_workcenter in self):
            raise exceptions.UserError(
                _('The capacity must be strictly positive.'))


class MrpRoutingWorkcenterProductLine(models.Model):
    _name = 'mrp.routing.wc.product.line'
    _description = 'Mrp Routing Workcenter Product Line'

    # product_id = fields.Many2one('product.product', 'Product')
    category_id = fields.Many2one('product.category', string='Product Category')
    commodity_categ_id = fields.Many2one('product.commodity.code', string='Commodity Code')
    capacity = fields.Float(string='Yards Per Hour', default=1.0)
    time_start = fields.Float(string='Time before prod.', help="Time in minutes for the setup.")
    time_stop = fields.Float(string='Clean-up Time.', help="Time in minutes for the cleaning.")
    time_cycle_manual = fields.Float(string="Time Cycle Manual")
    mrp_routing_workcenter_id = fields.Many2one('mrp.routing.workcenter', 'Operation')



class MrpRoutingWorkcenterInterval(models.Model):
    _name = 'mrp.routing.wc.interval'
    _description = 'Mrp Routing Operation Intervals'

    # product_id = fields.Many2one('product.product', 'Product')
    qty_prod_gap = fields.Char(string="Quantity")
    qty_prod_gap_hrs = fields.Integer(string='Interval(Hrs)')
    mrp_routing_interval_id = fields.Many2one('mrp.routing.workcenter', 'Operation')