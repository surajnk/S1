import time

from odoo import models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

# States considered "To Process": reserved (assigned) as well as pickings
# still waiting on another operation or on product availability.
READY_STATES = ('assigned', 'confirmed', 'waiting')


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    def get_action_picking_tree_ready(self):
        # The kanban "To Process" button opens this action relying on the
        # 'available' search filter (Ready = assigned only). Set an explicit
        # domain instead so the list matches the widened count_picking_ready
        # below, and drop the narrower search default so it doesn't also
        # get applied on top.
        action = super().get_action_picking_tree_ready()
        action['domain'] = [('state', 'in', READY_STATES)]
        action['context'].pop('search_default_available', None)
        return action

    def _compute_picking_count(self):
        # Same as stock.picking.type._compute_picking_count(), except
        # 'count_picking_ready' (the "To Process" kanban counter) also
        # includes pickings in 'waiting' and 'confirmed' states, not just
        # fully reserved ('assigned') ones.
        domains = {
            'count_picking_draft': [('state', '=', 'draft')],
            'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting'))],
            'count_picking_ready': [('state', 'in', READY_STATES)],
            'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed'))],
            'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed'))],
            'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting'))],
        }
        for field in domains:
            data = self.env['stock.picking'].read_group(domains[field] +
                [('state', 'not in', ('done', 'cancel')), ('picking_type_id', 'in', self.ids)],
                ['picking_type_id'], ['picking_type_id'])
            count = {
                x['picking_type_id'][0]: x['picking_type_id_count']
                for x in data if x['picking_type_id']
            }
            for record in self:
                record[field] = count.get(record.id, 0)
        for record in self:
            record.rate_picking_late = record.count_picking and record.count_picking_late * 100 / record.count_picking or 0
            record.rate_picking_backorders = record.count_picking and record.count_picking_backorders * 100 / record.count_picking or 0
