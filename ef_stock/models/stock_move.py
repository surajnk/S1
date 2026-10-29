from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    # Refinement of 'assigned' for Pick Components: available AND formally
    # pulled via a Material Request. Never applied to moves that aren't
    # already 'assigned', so stock's reservation engine (_action_assign,
    # which only looks at 'confirmed'/'waiting'/'partially_available') is
    # untouched.
    state = fields.Selection(
        selection_add=[('requested', 'Requested')],
        ondelete={'requested': lambda recs: recs.write({'state': 'assigned'})},
    )

    def _action_assign(self):
        res = super()._action_assign()

        productions = self.mapped('raw_material_production_id').filtered(lambda p: p)
        for production in productions:
            first_wo = production.workorder_ids.sorted('sequence')[:1]
            if not first_wo or not first_wo.workcenter_id.location_id:
                continue
            workcenter_location = first_wo.workcenter_id.location_id

            moves = self.filtered(
                lambda m: m.raw_material_production_id == production
                and m.state not in ('done', 'cancel')
            )
            if not moves:
                continue

            moves.filtered(
                lambda m: m.location_dest_id != workcenter_location
            ).write({'location_dest_id': workcenter_location.id})

            move_lines = moves.mapped('move_line_ids').filtered(
                lambda ml: ml.state not in ('done', 'cancel')
                and ml.location_dest_id != workcenter_location
            )
            if move_lines:
                move_lines.write({'location_dest_id': workcenter_location.id})
                _logger.info(
                    "[MO %s] _action_assign: forced %s move line(s) dest to %s",
                    production.name, len(move_lines), workcenter_location.complete_name,
                )

        to_promote = self.filtered(
            lambda m: m.state == 'assigned'
            and m.picking_id.picking_type_id.sequence_code == 'PC'
            and m.picking_id._has_active_material_request()
        )
        if to_promote:
            to_promote.write({'state': 'requested'})

        return res
