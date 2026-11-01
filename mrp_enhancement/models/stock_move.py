# -*- coding: utf-8 -*-
from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

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
                             'partially_available', 'assigned'])], limit=1)
