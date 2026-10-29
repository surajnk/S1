from odoo import models


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def get_action_picking_tree_ready(self):
        # Every operation type except Pick Components keeps stock's default
        # "To Process" (Ready/assigned) drill-down untouched.
        action = super().get_action_picking_tree_ready()
        if self.sequence_code == 'PC':
            # Pick Components: "To Process" = available AND formally
            # requested via a Material Request (see stock.move's
            # 'requested' state), matching count_picking_ready below.
            action['domain'] = [('state', '=', 'requested')]
            action['context'].pop('search_default_available', None)
        return action

    def _compute_picking_count(self):
        # Base behaviour (count_picking_ready = assigned-only, etc.) for
        # every operation type, Pick Components included.
        super()._compute_picking_count()

        pc_types = self.filtered(lambda t: t.sequence_code == 'PC')
        if not pc_types:
            return

        # Pick Components overrides "To Process": only count components
        # that have been formally requested, not every available one.
        data = self.env['stock.picking'].read_group(
            [
                ('state', '=', 'requested'),
                ('picking_type_id', 'in', pc_types.ids),
            ],
            ['picking_type_id'], ['picking_type_id'],
        )
        count_by_type = {
            x['picking_type_id'][0]: x['picking_type_id_count']
            for x in data if x['picking_type_id']
        }
        for picking_type in pc_types:
            picking_type.count_picking_ready = count_by_type.get(picking_type.id, 0)
