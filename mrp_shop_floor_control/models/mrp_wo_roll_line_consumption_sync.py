# -*- coding: utf-8 -*-

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class MrpWoRollLineConsumptionSync(models.Model):
    _inherit = 'mrp.wo.roll.line'

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._sync_raw_move_consumed()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if 'consumed_qty' in vals or 'prev_roll_id' in vals:
            self._sync_raw_move_consumed()
        return res

    def _get_component_moves_for_workorder(self, workorder):

        moves = workorder.production_id.move_raw_ids

        if 'curr_comp' in moves._fields and 'component_workorder_ids' in moves._fields:
            tier1 = moves.filtered(
                lambda m: m.curr_comp and (workorder in m.component_workorder_ids)
            )
            if tier1:
                return tier1

        tier2 = moves.filtered(
            lambda m: m.x_comp_operation and
                      m.x_comp_operation.name == workorder.operation_id.name
        )
        if tier2:
            return tier2

        bom_lines = workorder.production_id.bom_id.bom_line_ids.filtered(
            lambda l: workorder.operation_id in l.workcenter_capacities
        )
        if bom_lines:
            tier3_products = bom_lines.mapped('product_id')
            return moves.filtered(lambda m: m.product_id in tier3_products)

        return moves

    def _sync_raw_move_consumed(self):
        for rec in self:
            if not rec.prev_roll_id or not rec.workorder_id:
                continue

            production = rec.workorder_id.production_id
            if not production:
                continue
            lot = rec.prev_roll_id.lot_id
            if not lot and rec.prev_roll_id.name:
                lot = self.env['stock.production.lot'].search([
                    ('name', '=', rec.prev_roll_id.name),
                    ('company_id', '=', production.company_id.id),
                ], limit=1)
            if not lot:
                continue

            candidate_moves = self._get_component_moves_for_workorder(rec.workorder_id)
            raw_move = candidate_moves.filtered(
                lambda m: m.product_id == lot.product_id and m.state not in ('cancel',)
            )[:1]

            if not raw_move:
                _logger.warning(
                    "RAW CONSUMED SYNC: MO=%s WO=%s lot=%s product=%s - no "
                    "matching raw move found (checked WO-specific moves), "
                    "skipping sync",
                    production.name, rec.workorder_id.name, lot.name,
                    lot.product_id.display_name,
                )
                continue

            total_consumed = sum(
                self.env['mrp.wo.roll.line'].search([
                    ('prev_roll_id', '=', rec.prev_roll_id.id),
                    ('workorder_id.production_id', '=', production.id),
                ]).mapped('consumed_qty')
            )

            # total_consumed = sum(
            #     self.env['mrp.wo.roll.line'].search([
            #         ('prev_roll_id', '=', rec.prev_roll_id.id)
            #     ]).mapped('consumed_qty')
            # )

            existing_line = raw_move.move_line_ids.filtered(lambda ml: ml.lot_id == lot)

            if existing_line:
                if existing_line[0].qty_done != total_consumed:
                    existing_line[0].with_context(skip_remained_update=True).write({
                        'qty_done': total_consumed,
                    })
                    _logger.info(
                        "RAW CONSUMED SYNC (update): MO=%s WO=%s lot=%s "
                        "qty_done set to %s",
                        production.name, rec.workorder_id.name, lot.name,
                        total_consumed,
                    )
            else:
                self.env['stock.move.line'].create({
                    'move_id': raw_move.id,
                    'picking_id': raw_move.picking_id.id,
                    'product_id': lot.product_id.id,
                    'product_uom_id': raw_move.product_uom.id,
                    'location_id': raw_move.location_id.id,
                    'location_dest_id': raw_move.location_dest_id.id,
                    'lot_id': lot.id,
                    'product_uom_qty': 0.0,  # never reserved
                    'qty_done': total_consumed,
                    'company_id': raw_move.company_id.id,
                })
                _logger.info(
                    "RAW CONSUMED SYNC (new line): MO=%s WO=%s lot=%s "
                    "qty_done=%s created under move=%s",
                    production.name, rec.workorder_id.name, lot.name,
                    total_consumed, raw_move.id,
                )