from odoo import fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    # Refinement of 'assigned' for Pick Components: available AND formally
    # pulled via a Material Request (see stock.picking's _sync_requested_state
    # and action_assign, which are the only places that write this value).
    state = fields.Selection(
        selection_add=[('requested', 'Requested')],
        ondelete={'requested': lambda recs: recs.write({'state': 'assigned'})},
    )
