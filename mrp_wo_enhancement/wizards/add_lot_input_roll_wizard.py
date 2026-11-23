# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AddLotInputRollWizard(models.TransientModel):
    _name = 'add.lot.input.roll.wizard'
    _description = 'Add Stock Lot as Input Roll'

    workorder_id = fields.Many2one(
        'mrp.workorder', string='Work Order', required=True, readonly=True)
    lot_id = fields.Many2one(
        'stock.production.lot', string='Lot/Serial Number', required=True)
    product_id = fields.Many2one(
        'product.product', string='Product', readonly=True)
    available_qty = fields.Float(
        string='Available Qty', readonly=True,
        digits='Product Unit of Measure')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self._context.get('active_ids') or []
        if len(active_ids) > 1:
            raise UserError(_('Please select only one work order.'))
        if active_ids:
            res['workorder_id'] = active_ids[0]
        return res

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        self.product_id = self.lot_id.product_id
        self.available_qty = self._get_lot_available_qty(self.lot_id)

    @api.model
    def _get_lot_available_qty(self, lot):
        """On-hand quantity of the lot in internal locations."""
        if not lot:
            return 0.0
        quants = self.env['stock.quant'].sudo().search([
            ('lot_id', '=', lot.id),
            ('location_id.usage', '=', 'internal'),
        ])
        return sum(quants.mapped('quantity'))

    def action_add(self):
        self.ensure_one()
        wo = self.workorder_id
        lot = self.lot_id
        if not lot:
            raise UserError(_('Please select a lot.'))

        components = wo.production_id.move_raw_ids.filtered(
            lambda m: m.state != 'cancel').mapped('product_id')
        if lot.product_id not in components:
            raise UserError(_(
                'Product %s of lot %s is not a component of manufacturing '
                'order %s, so it cannot be added as an input roll.'
            ) % (lot.product_id.display_name, lot.name,
                 wo.production_id.name))

        if wo.prev_roll_line_ids.filtered(
                lambda l: l.roll_id and l.roll_id.name == lot.name):
            raise UserError(_(
                'Lot %s is already in the input rolls of work order %s.'
            ) % (lot.name, wo.display_name))

        qty = self._get_lot_available_qty(lot)
        if qty <= 0:
            raise UserError(_(
                'Lot %s has no available stock.') % lot.name)

        Roll = self.env['mrp.production.roll']
        roll = Roll.search([('name', '=', lot.name)], limit=1)
        if not roll:
            roll = Roll.create({'name': lot.name, 'total_qty': qty})

        self.env['mrp.wo.roll.line'].create({
            'roll_id': roll.id,
            'quantity': qty,
            'prev_work_order_id': wo.id,
            'user_id': self.env.user.id,
        })
        return {'type': 'ir.actions.act_window_close'}
