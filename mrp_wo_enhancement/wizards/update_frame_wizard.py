# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class UpdateFrameWizard(models.TransientModel):
    _name = 'update.frame.wizard'
    _description = 'Update Frame No on Pick Component Transfers'

    frame_no = fields.Char(string='Frame No', required=True)
    workorder_ids = fields.Many2many(
        'mrp.workorder',
        string='Work Orders',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self._context.get('active_ids', [])
        if active_ids:
            res['workorder_ids'] = [(6, 0, active_ids)]
        return res

    def action_apply(self):
        productions = self.workorder_ids.mapped('production_id')
        if not productions:
            raise UserError(_('No Manufacturing Orders found for the selected workorders.'))

        # Filter Pick Component transfers using sequence_code='PC'
        # catches original transfer + all backorders
        pickings = self.env['stock.picking'].search([
            ('origin', 'in', productions.mapped('name')),
            ('state', 'not in', ('cancel',)),
            ('is_reverse_transfer', '=', False),
        ]).filtered(
            lambda p: p.picking_type_id.sequence_code == 'PC'
        )

        if not pickings:
            raise UserError(_(
                'No Pick Component transfers found for the selected workorders.'
            ))

        pickings.write({'x_frame_no': self.frame_no})
        _logger.info(
            "Updated x_frame_no=%s on pick component pickings=%s for MOs=%s",
            self.frame_no, pickings.ids, productions.mapped('name')
        )
        return {'type': 'ir.actions.act_window_close'}