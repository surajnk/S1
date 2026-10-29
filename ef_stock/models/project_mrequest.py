from odoo import models


class MaterialRequest(models.Model):
    _inherit = 'project.mrequest'

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') == 'reject':
            pickings = self.env['stock.picking'].search([
                ('mrequest_id', 'in', self.ids),
                ('picking_type_id.sequence_code', '=', 'PC'),
            ])
            requested_moves = pickings.move_lines.filtered(lambda m: m.state == 'requested')
            if requested_moves:
                requested_moves.write({'state': 'assigned'})
        return res
