# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging
import traceback

_logger = logging.getLogger(__name__)

class StockMove(models.Model):

    _inherit = 'stock.move'

    x_comp_operation = fields.Many2one('mrp.routing.workcenter',string='Operation', domain="[('id', 'in', x_listed_operations)]")
    x_listed_operations = fields.Many2many('mrp.routing.workcenter')

    @api.onchange('production_id')
    def _onchange_production_id(self):
        for move in self:
            operation_ids = self.env['mrp.routing.workcenter']
            if move.production_id:
                production = move.production_id
                for wo in production.workorder_ids:
                    operation_ids |= wo.operation_id
            move.x_listed_operations = operation_ids

    @api.model
    def default_get(self, fields):
        defaults = super().default_get(fields)
        # Perform computations or fetch data here to set default values
        defaults['x_listed_operations'] = self._compute_x_listed_operations()
        _logger.info("1111111'%s'",defaults['x_listed_operations'])
        return defaults
 

    @api.depends('production_id.move_raw_ids')
    def _compute_x_listed_operations(self):
        operation_ids = self.env['mrp.routing.workcenter']
        for production in self.production_id:
            for wo in production.workorder_ids:
                operation_ids |= wo.operation_id
        _logger.info("22222222'%s'",operation_ids)
        return [(6, 0, operation_ids.ids)]
   

    def open_on_hand_qty(self):
        """
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Product Quantity',
            'view_mode': 'tree,form',
            'res_model': 'stock.quant',
            'domain': [['product_id', '=', self.product_id.id]],
            'context': {'default_product_id': self.product_id.id},
            'target': 'new'
        }

    def _assign_picking(self):
        mrp_raw = self.filtered(lambda m: m.raw_material_production_id)
        if mrp_raw:
            _logger.info("=== _assign_picking called for MRP raw moves: %s", mrp_raw.mapped('product_id.name'))
            _logger.info("=== Stack: %s", ''.join(traceback.format_stack()[-6:]))
        return super()._assign_picking()

    # def _assign_picking(self):
    #     """
    #     Before assigning to picking, merge duplicate raw material moves
    #     for same product+UoM within same production order.
    #     """
    #     # Only process MRP raw material moves
    #     mrp_raw = self.filtered(lambda m: m.raw_material_production_id and m.state not in ('done', 'cancel'))
        
    #     if mrp_raw:
    #         merged_ids_to_cancel = self.env['stock.move']
    #         seen = {}

    #         for move in mrp_raw:
    #             key = (
    #                 move.raw_material_production_id.id,
    #                 move.product_id.id,
    #                 move.product_uom.id,
    #                 move.location_id.id,
    #                 move.location_dest_id.id,
    #             )
    #             if key not in seen:
    #                 seen[key] = move
    #             else:
    #                 seen[key].product_uom_qty += move.product_uom_qty
    #                 merged_ids_to_cancel |= move

    #         if merged_ids_to_cancel:
    #             merged_ids_to_cancel.write({'state': 'cancel'})
    #             merged_ids_to_cancel.unlink()

    #         # Only pass non-cancelled moves to super
    #         return super(StockMove, self - merged_ids_to_cancel)._assign_picking()

    #     return super(StockMove, self)._assign_picking()