# -*- coding: utf-8 -*-
import logging
import traceback

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        # Diagnostic, off by default: set the system parameter
        # mrp_enhancement.log_raw_move_create to 1 to log where a component
        # move comes from when its MO already has an open move of the same
        # product (to find what adds an extra line next to the BOM's).
        if str(self.env['ir.config_parameter'].sudo().get_param(
                'mrp_enhancement.log_raw_move_create', '0')).strip().lower() \
                in ('1', 'true', 'yes'):
            for move in moves.filtered('raw_material_production_id'):
                same = move.raw_material_production_id.move_raw_ids.filtered(
                    lambda m: m != move and m.product_id == move.product_id
                    and m.state != 'cancel')
                if same:
                    _logger.warning(
                        "RAW MOVE DUPLICATE: move=%s mo=%s product=%s bom_line=%s "
                        "demand=%s state=%s others=%s created from:\n%s",
                        move.id, move.raw_material_production_id.name,
                        move.product_id.display_name, move.bom_line_id.id,
                        move.product_uom_qty, move.state, same.ids,
                        ''.join(traceback.format_stack(limit=30)))
        return moves

    x_pc_split = fields.Boolean(
        string='Split by Operation',
        copy=True,
        help="Pick Components move whose destination follows the first "
             "operation under the BOM line's Multiple Operations, instead of "
             "the first work order's workcenter.",
    )

    x_final_roll_line_id = fields.Many2one(
        'final.wo.roll',
        string='Final Roll Line',
        copy=False,
        index=True,
        ondelete='set null',
        help="Final roll line whose consumption caused this stock move "
             "(input roll leaving / returning to the last workorder's "
             "workcenter location).",
    )

    x_final_roll_input_id = fields.Many2one(
        'final.wo.roll.input',
        string='Final Roll Input Line',
        copy=False,
        index=True,
        ondelete='set null',
        help="Input line of a final roll line whose consumption caused this "
             "stock move (used when a final roll line has several input "
             "rolls; x_final_roll_line_id covers the single-roll case).",
    )

    def _get_operation_split_location(self):
        """Workcenter location of the first operation (by sequence) under
        the "Multiple Operations" of the BOM line behind this MO raw move,
        or an empty recordset when the line has no such operation or the
        workcenter has no location."""
        self.ensure_one()
        operations = self.bom_line_id.workcenter_capacities.sorted(
            lambda op: (op.sequence, op.id))[:1]
        return operations.workcenter_id.location_id

    def _get_new_picking_values(self):
        vals = super()._get_new_picking_values()
        if any(self.mapped('x_pc_split')):
            vals['x_pc_split'] = True
        return vals

    def _search_picking_for_assignation(self):
        """Never mix split and standard Pick Components moves in one
        transfer, even when they end up with the same destination."""
        self.ensure_one()
        return self.env['stock.picking'].search([
            ('group_id', '=', self.group_id.id),
            ('location_id', '=', self.location_id.id),
            ('location_dest_id', '=', self.location_dest_id.id),
            ('picking_type_id', '=', self.picking_type_id.id),
            ('printed', '=', False),
            ('immediate_transfer', '=', False),
            ('x_pc_split', '=', self.x_pc_split),
            ('state', 'in', ['draft', 'confirmed', 'waiting',
                             'partially_available', 'assigned', 'requested'])], limit=1)
