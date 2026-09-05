# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

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

    def unlink(self):
        extra_allowed = self.filtered(
            lambda m: m.state == 'confirmed'
            and not m.reserved_availability
            and not any(m.move_line_ids.mapped('qty_done'))
        )
        rest = self - extra_allowed

        if extra_allowed:
            _logger.info(
                "[GTS DEBUG unlink] cancelling (not deleting) confirmed-but-unreserved "
                "moves instead, to avoid the unlink+state-flip hang seen earlier: %s",
                extra_allowed.ids,
            )
            extra_allowed.write({'state': 'cancel'})

        if rest:
            return super(StockMove, rest).unlink()
        return True

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
