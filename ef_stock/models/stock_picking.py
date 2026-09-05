import inspect

from odoo import api,models, fields
from odoo.exceptions import UserError
from odoo.tools.translate import _
import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    ship_via_id = fields.Many2one(
        'ship.via',
        string='Ship Via',
        copy=True,
    )

    scheduled_date_only = fields.Date(
        string='Scheduled Date',
        compute='_compute_date_only_fields',
        store=True,
    )
    date_deadline_only = fields.Date(
        string='Deadline',
        compute='_compute_date_only_fields',
        store=True,
    )

    is_reverse_transfer = fields.Boolean(
        string='Is Reverse Transfer',
        default=False,
    )
    
    tow_user_id = fields.Many2one(
        'res.users',
        string='TOW Operator',
        compute='_compute_tow_user_id',
        store=True,
    )

    @api.depends('move_lines.product_id.categ_id')
    def _compute_tow_user_id(self):
        for picking in self:
            categories = picking.move_lines.mapped('product_id.categ_id')
            _logger.info(
                "_compute_tow_user_id: picking=%s categories=%s",
                picking.name, categories.mapped('name')
            )
            tow_user = False
            for categ in categories:
                current = categ
                while current:
                    _logger.info(
                        "_compute_tow_user_id: checking categ=%s tow_user_id=%s",
                        current.name, current.tow_user_id
                    )
                    if current.tow_user_id:
                        tow_user = current.tow_user_id
                        break
                    current = current.parent_id
                if tow_user:
                    break
            _logger.info(
                "_compute_tow_user_id: picking=%s tow_user=%s",
                picking.name, tow_user
            )
            picking.tow_user_id = tow_user
 
    @api.depends('scheduled_date', 'date_deadline')
    def _compute_date_only_fields(self):
        for picking in self:
            picking.scheduled_date_only = picking._to_date_only(picking.scheduled_date)
            picking.date_deadline_only = picking._to_date_only(picking.date_deadline)
 
    @staticmethod
    def _to_date_only(dt_value):
        if not dt_value:
            return False
        return dt_value.date()


    def _create_backorder(self, backorder_moves=None):
        parent_method = super(StockPicking, self)._create_backorder
        signature_params = inspect.signature(parent_method).parameters

        if 'backorder_moves' in signature_params:
            backorders = parent_method(backorder_moves=backorder_moves)
        elif backorder_moves is not None:
            backorders = parent_method(backorder_moves)
        else:
            backorders = parent_method()
        for backorder in backorders:
            if (
                not backorder.ship_via_id
                and backorder.backorder_id
                and backorder.backorder_id.ship_via_id
            ):
                backorder.ship_via_id = backorder.backorder_id.ship_via_id
        return backorders

    def create_bill_of_leading(self):
        list = []
        parnet_id = 0
        for rec in self:
            list.append(rec.id)
            parnet_id = rec.partner_id.id
        view_id = self.env.ref('ef_stock.bill_of_leading_wiz_form_view').id
        context = {
                'default_partner_id': parnet_id,
                'default_delivery_order_ids': list

        }
        return {
                'type': 'ir.actions.act_window',
                'name': 'Bill of Leading',
                'view_mode': 'tree',
                'view_type': 'form',
                'res_model': 'bill.of.leading.wiz',
                'view_id': view_id,
                'views': [(view_id, 'form')],
                'target': 'new',
                'context': context
        }

    # def action_view_packages(self):
    #     self.ensure_one()
    #     packages = self.move_line_ids.mapped('result_package_id').filtered(lambda p: p)
    #     packages = packages.browse(set(packages.ids))
    #     return {
    #         'name': 'Packages - %s' % self.name,
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'stock.quant.package',
    #         'view_mode': 'tree,form',
    #         'domain': [('id', 'in', packages.ids)],
    #         'target': 'new',
    #     }
    def action_view_packages(self):
        self.ensure_one()
        packages = self.move_line_ids.mapped('result_package_id').filtered(lambda p: p)
        packages = packages.browse(set(packages.ids))
        return {
            'name': 'Packages - %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant.package',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', packages.ids)],
            'context': {'create': False},
        }


    def action_assign(self):
        res = super().action_assign()
        for picking in self:
            if picking.picking_type_id.sequence_code != 'PC':
                continue
            production = None
            for move in picking.move_ids_without_package:
                if move.raw_material_production_id:
                    production = move.raw_material_production_id
                    break
            if not production and picking.origin:
                production = self.env['mrp.production'].search([
                    ('name', '=', picking.origin)
                ], limit=1)
            if not production:
                continue
            first_wo = production.workorder_ids.sorted('sequence')[:1]
            if not first_wo or not first_wo.workcenter_id.location_id:
                continue
            workcenter_location = first_wo.workcenter_id.location_id
            picking.move_line_ids.filtered(
                lambda ml: ml.state not in ('done', 'cancel')
            ).write({'location_dest_id': workcenter_location.id})
            _logger.info(
                "action_assign: forced move lines dest to %s for picking %s",
                workcenter_location.name, picking.name,
            )
        return res

    def write(self, vals):
        result = super().write(vals)
        # When moves are added to a picking, check if it's a PC picking for an MO
        if 'move_ids_without_package' in vals or 'move_lines' in vals:
            self._sync_mo_workcenter_location()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        pickings = super().create(vals_list)
        pickings._sync_mo_workcenter_location()
        return pickings

    def button_validate(self):
        res = super().button_validate()

        if self.env.context.get('skip_roll_transfer_move'):
            return res

        for picking in self:
            if picking.picking_type_code != 'internal' or not picking.origin:
                continue

            if picking.is_reverse_transfer:  # ← skip
                continue

            production = self.env['mrp.production'].search([
                ('name', '=', picking.origin)
            ], limit=1)
            if not production:
                continue

            wo_by_location = {}
            for wo in production.workorder_ids:
                if wo.workcenter_id and wo.workcenter_id.location_id:
                    wo_by_location[wo.workcenter_id.location_id.id] = wo

            source_wo = wo_by_location.get(picking.location_id.id)

            # Skip if source location is Virtual/Inventory (receipt move from _create_wc_receipt_move)
            # Those are system moves to seed stock, not actual WC transfers
            inventory_loc = self.env.ref('stock.location_inventory', raise_if_not_found=False)
            if inventory_loc and picking.location_id.id == inventory_loc.id:
                continue

            for ml in picking.move_line_ids:
                if not ml.lot_id or not ml.qty_done:
                    continue

                if ml.location_id.id == ml.location_dest_id.id:
                    continue

                dest_loc = ml.location_dest_id
                dest_wo = wo_by_location.get(dest_loc.id)

                if not dest_wo:
                    continue

                # Only backward or same WC moves (defective/rework)
                if source_wo and dest_wo.sequence > source_wo.sequence:
                    continue

                # Skip if source and dest WO are the same
                if source_wo and dest_wo.id == source_wo.id:
                    continue

                roll = self.env['mrp.production.roll'].search([
                    ('name', '=', ml.lot_id.name)
                ], limit=1)
                if not roll:
                    roll = self.env['mrp.production.roll'].create({
                        'name': ml.lot_id.name,
                        'total_qty': ml.qty_done,
                    })

                exists = dest_wo.prev_roll_line_ids.filtered(
                    lambda l: l.roll_id.id == roll.id
                )
                if not exists:
                    self.env['mrp.wo.roll.line'].with_context(
                        skip_roll_transfer_move=True
                    ).create({
                        'roll_id': roll.id,
                        'quantity': ml.qty_done,
                        'prev_work_order_id': dest_wo.id,
                        'user_id': self.env.uid,
                    })
                else:
                    exists[0].write({'quantity': ml.qty_done})

        return res
    # def button_validate(self):
    #     res = super().button_validate()

    #     if self.env.context.get('skip_roll_transfer_move'):
    #         return res

    #     for picking in self:
    #         if picking.picking_type_code != 'internal' or not picking.origin:
    #             continue

    #         production = self.env['mrp.production'].search([
    #             ('name', '=', picking.origin)
    #         ], limit=1)
    #         if not production:
    #             continue

    #         wo_by_location = {}
    #         for wo in production.workorder_ids:
    #             if wo.workcenter_id and wo.workcenter_id.location_id:
    #                 wo_by_location[wo.workcenter_id.location_id.id] = wo

    #         source_wo = wo_by_location.get(picking.location_id.id)

    #         for ml in picking.move_line_ids:
    #             if not ml.lot_id or not ml.qty_done:
    #                 continue

    #             if ml.location_id.id == ml.location_dest_id.id:
    #                 continue

    #             dest_loc = ml.location_dest_id
    #             dest_wo = wo_by_location.get(dest_loc.id)

    #             if not dest_wo:
    #                 continue

    #             # Only backward or same WC moves (defective/rework)
    #             if source_wo and dest_wo.sequence > source_wo.sequence:
    #                 continue

    #             roll = self.env['mrp.production.roll'].search([
    #                 ('name', '=', ml.lot_id.name)
    #             ], limit=1)
    #             if not roll:
    #                 roll = self.env['mrp.production.roll'].create({
    #                     'name': ml.lot_id.name,
    #                     'total_qty': ml.qty_done,
    #                 })

    #             exists = dest_wo.prev_roll_line_ids.filtered(
    #                 lambda l: l.roll_id.id == roll.id
    #             )
    #             if not exists:
    #                 self.env['mrp.wo.roll.line'].with_context(
    #                     skip_roll_transfer_move=True
    #                 ).create({
    #                     'roll_id': roll.id,
    #                     'quantity': ml.qty_done,
    #                     'prev_work_order_id': dest_wo.id,
    #                     'user_id': self.env.uid,
    #                 })
    #             else:
    #                 exists[0].write({'quantity': ml.qty_done})

    #     return res
    def _sync_mo_workcenter_location(self):
        for picking in self:

            _logger.info(
                "_sync_mo_workcenter_location: picking=%s type=%s origin=%s",
                picking.name,
                picking.picking_type_id.sequence_code,
                picking.origin,
            )

            inventory_loc = self.env.ref('stock.location_inventory', raise_if_not_found=False)
            if inventory_loc and picking.location_id.id == inventory_loc.id:
                continue
            # Only PC pickings
            if picking.picking_type_id.sequence_code != 'PC':
                warehouse = picking.picking_type_id.warehouse_id
                if not (warehouse and picking.picking_type_id == warehouse.pbm_type_id):
                    continue

            # Find MO via move's raw_material_production_id
            production = None
            for move in picking.move_ids_without_package:
                if move.raw_material_production_id:
                    production = move.raw_material_production_id
                    break

            # Fallback: find via origin/name match
            if not production and picking.origin:
                production = self.env['mrp.production'].search([
                    ('name', '=', picking.origin)
                ], limit=1)

            if not production:
                _logger.info("[Picking %s] _sync: no MO found", picking.name)
                continue

            first_wo = production.workorder_ids.sorted('sequence')[:1]
            if not first_wo or not first_wo.workcenter_id.location_id:
                _logger.info("[Picking %s] _sync: MO %s has no workcenter location", picking.name, production.name)
                continue

            workcenter_location = first_wo.workcenter_id.location_id

            pc_moves = picking.move_ids_without_package.filtered(
                lambda m: m.state not in ('done', 'cancel')
            )
            to_unreserve = pc_moves.filtered(lambda m: m.state in ('assigned', 'partially_available'))
            if to_unreserve:
                to_unreserve._do_unreserve()

            picking.location_dest_id = workcenter_location
            pc_moves.write({'location_dest_id': workcenter_location.id})
            pc_moves.mapped('move_line_ids').write({'location_dest_id': workcenter_location.id})
            pc_moves._action_assign()

            _logger.info(
                "[Picking %s] synced location_dest_id=%s from MO %s",
                picking.name, workcenter_location.complete_name, production.name
            )
    

