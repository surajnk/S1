# -*- coding: utf-8 -*-
from odoo import models


class StockRule(models.Model):
    _inherit = 'stock.rule'

    def _is_pick_components_rule(self):
        """True for the manufacturing pull rule that creates Pick Components
        (PC) transfers feeding the raw moves of an MO."""
        self.ensure_one()
        picking_type = self.picking_type_id
        if not picking_type:
            return False
        warehouse = picking_type.warehouse_id
        return picking_type.sequence_code == 'PC' or bool(
            warehouse and picking_type == warehouse.pbm_type_id)

    def _get_stock_move_values(self, product_id, product_qty, product_uom,
                               location_id, name, origin, company_id, values):
        """Route a Pick Components move to the workcenter location of the
        first operation under the BOM line's "Multiple Operations".

        The destination is set when the move is created, so the standard
        picking assignment (which groups moves by destination) puts the
        components of one operation in one transfer and the components of
        another operation in another. Nothing is rewritten afterwards, i.e.
        nothing runs inside ``stock.move._action_confirm``. BOM lines without
        operations keep the standard behaviour.
        """
        move_values = super()._get_stock_move_values(
            product_id, product_qty, product_uom, location_id, name, origin,
            company_id, values)
        if not self._is_pick_components_rule():
            return move_values
        raw_moves = (values.get('move_dest_ids') or self.env['stock.move']).filtered(
            'raw_material_production_id')
        if len(raw_moves) == 1:
            location = raw_moves._get_operation_split_location()
            if location:
                move_values['location_dest_id'] = location.id
                move_values['x_pc_split'] = True
        return move_values
