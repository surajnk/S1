# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RollTransferWizard(models.TransientModel):
    _name = 'roll.transfer.wizard'
    _description = 'Roll Transfer State Wizard'

    transfer_line_ids = fields.One2many(
        'roll.transfer.wizard.line',
        'wizard_id',
        string='Transfers',
    )

    frame_no = fields.Char(string='Frame No')

    def action_put_on_hold(self):
        _logger.info(
            "action_put_on_hold: all lines=%s selected=%s",
            self.transfer_line_ids.ids,
            self.transfer_line_ids.mapped('selected'),
        )
        selected = self.transfer_line_ids.filtered(
            lambda l: l.selected and l.state not in ('done', 'cancel', 'waiting')
        )
        _logger.info("action_put_on_hold: selected lines=%s", selected.ids)

        if not selected:
            raise UserError(_("Please select at least one transfer to put on hold."))

        for line in selected:
            picking = line.picking_id.sudo()
            picking.write({'state': 'waiting'})
            picking.move_lines.write({'state': 'waiting'})
            line.write({'state': 'waiting', 'selected': False})

        return self._reopen()

    def action_release(self):
        _logger.info(
            "action_release: all lines=%s selected=%s",
            self.transfer_line_ids.ids,
            self.transfer_line_ids.mapped('selected'),
        )
        selected = self.transfer_line_ids.filtered(
            lambda l: l.selected and l.state == 'waiting'
        )
        _logger.info("action_release: selected lines=%s", selected.ids)

        if not selected:
            raise UserError(_("Please select at least one waiting transfer to release."))

        for line in selected:
            picking = line.picking_id.sudo()
            picking.write({'state': 'confirmed'})
            picking.move_lines.filtered(
                lambda m: m.state == 'waiting'
            ).write({'state': 'confirmed'})
            picking.action_assign()
            line.write({'state': picking.state, 'selected': False})

        return self._reopen()

    def action_create_reverse_move(self):
        selected = self.transfer_line_ids.filtered(
            lambda l: l.selected and l.state == 'done'
        )

        if not selected:
            raise UserError(_("Please select at least one validated (Done) transfer."))

        created_pickings = []

        for line in selected:
            picking = line.picking_id
            wo = line.workorder_id
            target_wo = line.target_workorder_id

            if not target_wo or not target_wo.workcenter_id or not target_wo.workcenter_id.location_id:
                raise UserError(_(
                    "No destination workcenter location found for the selected workorder on transfer %s."
                ) % picking.name)
            dest_loc = target_wo.workcenter_id.location_id
            if not dest_loc:
                raise UserError(_(
                    "No destination location found on transfer %s."
                ) % picking.name)
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal'),
                ('warehouse_id.company_id', '=', wo.company_id.id),
            ], limit=1)

            origin = picking.origin or wo.production_id.name

            mo_key = '/'.join(wo.production_id.name.split('/')[-2:]) + '/'  # "MO/00320/"
            relevant_move_lines = picking.move_line_ids.filtered(
                lambda ml: ml.lot_id and mo_key in ml.lot_id.name
            )

            ml_by_dest = {}
            for ml in relevant_move_lines:
                actual_dest = ml.location_dest_id
                if actual_dest not in ml_by_dest:
                    ml_by_dest[actual_dest] = []
                ml_by_dest[actual_dest].append(ml)
            # ml_by_dest = {}
            # for ml in picking.move_line_ids:
            #     actual_dest = ml.location_dest_id
            #     if actual_dest not in ml_by_dest:
            #         ml_by_dest[actual_dest] = []
            #     ml_by_dest[actual_dest].append(ml)

            for actual_src_loc, move_lines in ml_by_dest.items():
                new_picking = self.env['stock.picking'].create({
                    'picking_type_id': picking_type.id,
                    'location_id': actual_src_loc.id,
                    'location_dest_id': dest_loc.id,
                    'origin': 'REV/' + origin,
                    'company_id': wo.company_id.id,
                    'move_type': 'direct',
                    'is_reverse_transfer': True,
                    'x_frame_no': self.frame_no or False,
                })

                for ml in move_lines:
                    new_move = self.env['stock.move'].create({
                        'name': ml.product_id.display_name,
                        'product_id': ml.product_id.id,
                        'product_uom': ml.product_uom_id.id,
                        'product_uom_qty': ml.qty_done,
                        'location_id': actual_src_loc.id,
                        'location_dest_id': dest_loc.id,
                        'picking_id': new_picking.id,
                        'origin': 'REV/' + origin,
                        'company_id': wo.company_id.id,
                        'production_id': False,
                        'raw_material_production_id': False,
                    })
                    if ml.lot_id:
                        self.env['stock.move.line'].create({
                            'move_id': new_move.id,
                            'picking_id': new_picking.id,
                            'product_id': ml.product_id.id,
                            'product_uom_id': ml.product_uom_id.id,
                            'location_id': actual_src_loc.id,
                            'location_dest_id': dest_loc.id,
                            'lot_id': ml.lot_id.id,
                            'qty_done': ml.qty_done,
                            'product_uom_qty': ml.qty_done,
                            'product_uom_qty': 0,
                        })

                new_picking.action_confirm()
                if new_picking.state == 'waiting':
                    new_picking.write({'state': 'confirmed'})
                # Do NOT call action_assign() — exact lot already set above
                new_picking.write({'state': 'assigned'})

                created_pickings.append(new_picking.name)

                _logger.info(
                    "Created reverse picking %s: %s → %s for WO %s",
                    new_picking.name, actual_src_loc.name,
                    dest_loc.name, wo.name,
                )

            line.write({'selected': False})

        # Show success notification then reopen wizard
        picking_names = ', '.join(created_pickings)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Reverse transfer(s) created: %s') % picking_names,
                'sticky': False,
                'type': 'success',
                'next': self._reopen(),
            }
        }

    # def action_create_reverse_move(self):
    #     selected = self.transfer_line_ids.filtered(
    #         lambda l: l.selected and l.state == 'done'
    #     )
    #     if not selected:
    #         raise UserError(_("Please select at least one validated (Done) transfer."))

    #     for line in selected:
    #         picking = line.picking_id
    #         wo = line.workorder_id

    #         # Destination = picking header's location_dest_id (e.g. RI/W/RI-EMB)
    #         dest_loc = picking.location_dest_id
    #         if not dest_loc:
    #             raise UserError(_(
    #                 "No destination location found on transfer %s."
    #             ) % picking.name)

    #         picking_type = self.env['stock.picking.type'].search([
    #             ('code', '=', 'internal'),
    #             ('warehouse_id.company_id', '=', wo.company_id.id),
    #         ], limit=1)

    #         origin = picking.origin or wo.production_id.name

    #         # Group move lines by their actual destination (e.g. RI/R/J5)
    #         ml_by_dest = {}
    #         for ml in picking.move_line_ids:
    #             actual_dest = ml.location_dest_id
    #             if actual_dest not in ml_by_dest:
    #                 ml_by_dest[actual_dest] = []
    #             ml_by_dest[actual_dest].append(ml)

    #         for actual_src_loc, move_lines in ml_by_dest.items():
    #             new_picking = self.env['stock.picking'].create({
    #                 'picking_type_id': picking_type.id,
    #                 'location_id': actual_src_loc.id,   # RI/R/J5
    #                 'location_dest_id': dest_loc.id,    # RI/W/RI-EMB
    #                 'origin': origin,
    #                 'company_id': wo.company_id.id,
    #                 'move_type': 'direct',
    #             })

    #             for ml in move_lines:
    #                 self.env['stock.move'].create({
    #                     'name': ml.product_id.display_name,
    #                     'product_id': ml.product_id.id,
    #                     'product_uom': ml.product_uom_id.id,
    #                     'product_uom_qty': ml.qty_done,
    #                     'location_id': actual_src_loc.id,
    #                     'location_dest_id': dest_loc.id,
    #                     'picking_id': new_picking.id,
    #                     'origin': origin,
    #                     'company_id': wo.company_id.id,
    #                 })

    #             new_picking.action_confirm()
    #             if new_picking.state == 'waiting':
    #                 new_picking.write({'state': 'confirmed'})
    #             new_picking.action_assign()

    #             _logger.info(
    #                 "Created reverse picking %s: %s → %s for WO %s",
    #                 new_picking.name, actual_src_loc.name,
    #                 dest_loc.name, wo.name,
    #             )

    #         line.write({'selected': False})

    #     return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'roll.transfer.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref(
                'mrp_enhancement.roll_transfer_wizard_form_view'
            ).id,
            'target': 'new',
            'context': self.env.context,
        }


class RollTransferWizardLine(models.TransientModel):
    _name = 'roll.transfer.wizard.line'
    _description = 'Roll Transfer Wizard Line'

    wizard_id = fields.Many2one(
        'roll.transfer.wizard',
        ondelete='cascade',
    )
    selected = fields.Boolean(string='Select', default=False)
    picking_id = fields.Many2one(
        'stock.picking',
        string='Transfer',
        readonly=True,
    )
    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        readonly=True,
    )
    target_workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Destination Work Order',
        readonly=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting'),
        ('confirmed', 'Confirmed'),
        ('assigned', 'Ready'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', readonly=True)
    location_id = fields.Many2one(
        related='picking_id.location_id',
        string='From',
        readonly=True,
    )
    location_dest_id = fields.Many2one(
        related='picking_id.location_dest_id',
        string='To',
        readonly=True,
    )