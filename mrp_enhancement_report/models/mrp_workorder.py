# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'
    _description = 'Work Order'

    width = fields.Char('Width')
    trim = fields.Char('Trim')
    # base_avail = fields.Char('Base Avail')
    base_avail = fields.Char('Base Avail', compute='_compute_base_avail', store=True)
    t_c = fields.Char('T/C')
    rod = fields.Integer('Rod')
    shaded = fields.Boolean('Shaded', default=False)
    wizard_id = fields.Integer('')
    timer_id = fields.Integer('Timer ID',copy=False)

    @api.depends(
    'production_id.move_raw_ids.curr_comp',
    'production_id.move_raw_ids.component_workorder_ids',
    'production_id.move_raw_ids.x_comp_operation',
    'production_id.move_raw_ids.product_id',
    'production_id.bom_id.bom_line_ids.workcenter_capacities',
    'operation_id',
    'workcenter_id',
    )
    def _compute_base_avail(self):
        for wo in self:
            moves = wo.production_id.move_raw_ids
            _logger.info("WO: %s | total move_raw_ids: %s", wo.name, len(moves))

            # Tier 1: curr_comp=True and this workorder is in component_workorder_ids
            curr_comp_moves = moves.filtered(
                lambda m: m.curr_comp and (wo in m.component_workorder_ids)
            )
            _logger.info("WO: %s | Tier1 curr_comp_moves: %s", wo.name, curr_comp_moves.mapped('product_id.display_name'))

            if curr_comp_moves:
                wo.base_avail = ', '.join(curr_comp_moves.mapped('product_id.display_name'))
                continue

            # Tier 2: fallback via x_comp_operation matching operation name
            fallback_moves = moves.filtered(
                lambda m: m.x_comp_operation and
                          m.x_comp_operation.name == wo.operation_id.name
            )
            _logger.info("WO: %s | Tier2 fallback_moves: %s", wo.name, fallback_moves.mapped('product_id.display_name'))

            if fallback_moves:
                wo.base_avail = ', '.join(fallback_moves.mapped('product_id.display_name'))
                continue

            # Tier 3: match via workcenter_capacities on BOM lines
            bom_lines = wo.production_id.bom_id.bom_line_ids.filtered(
                lambda l: wo.operation_id in l.workcenter_capacities
            )
            _logger.info("WO: %s | operation_id: %s | Tier3 bom_lines: %s", wo.name, wo.operation_id.name, bom_lines.mapped('product_id.display_name'))

            if bom_lines:
                wo.base_avail = ', '.join(bom_lines.mapped('product_id.display_name'))
                continue

            wo.base_avail = ''