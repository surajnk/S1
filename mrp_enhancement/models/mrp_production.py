# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare
import math
import logging

_logger = logging.getLogger(__name__)


class MRPProduction(models.Model):
    _inherit = 'mrp.production'

    # NOTE: inverse on a non-computed field is not triggered by Odoo automatically.
    # We will explicitly call _inverse_x_order_master_yards() from create/write/action_confirm.
    x_order_master_yards = fields.Integer('Required Master Yards', inverse="_inverse_x_order_master_yards")

    under_allowance = fields.Boolean(string="Under Allowance", default=False)
    over_allowance = fields.Boolean(string="Over Allowance", default=False)
    allowance_acknowledged = fields.Boolean(string="Allowances Acknowledged", default=False)

    customer_uom_put_up = fields.Float(string="Put up(Yards)", compute="_compute_customer_uom_put_up")

    qty_produced_db = fields.Float(
        string="Qty Produced (DB)",
        related='qty_produced',
        store=True,
        help="Stored mirror of qty_produced for SQL dashboards"
    )

    # --------------------------
    # ACTIONS
    # --------------------------
    def action_allowance_acknowledged(self):
        """Mark selected manufacturing orders as having allowances acknowledged."""
        self.write({'allowance_acknowledged': True})


    def _pre_button_mark_done(self):
        productions_to_immediate = self._check_immediate()
        if productions_to_immediate:
            return productions_to_immediate._action_generate_immediate_wizard()

        for production in self:
            if float_is_zero(production.qty_producing, precision_rounding=production.product_uom_id.rounding):
                if float_compare(production.qty_produced, production.product_qty,
                                  precision_rounding=production.product_uom_id.rounding) < 0:
                    raise UserError(_('The quantity to produce must be positive!'))

        consumption_issues = self._get_consumption_issues()
        if consumption_issues:
            return self._action_generate_consumption_wizard(consumption_issues)

        quantity_issues = self._get_quantity_produced_issues()
        if quantity_issues:
            return self._action_generate_backorder_wizard(quantity_issues)
        return True

    # --------------------------
    # COMPUTE
    # --------------------------

    @api.depends('uom_put_up')
    def _compute_customer_uom_put_up(self):
        for rec in self:
            rec.customer_uom_put_up = 0
            if rec.uom_put_up:
                customer_qty = rec.uom_put_up or 0
                customer_width = rec.x_order_line_customer_mrp_width or 1
                customer_length = rec.x_order_line_customer_mrp_length or '0.0'
                trim_width = rec.x_order_line_trim_width or 1
                trim_length = rec.x_order_line_trim_length or 1
                machine_length = rec.x_order_line_machine_length or 41
                component_width = rec.move_raw_ids[0].product_id.x_item_width or 1
                if customer_width == component_width:
                    _logger.info("CASE11111")
                    trim_width = 0
                    Width_Outs = (int(component_width - trim_width) / customer_width) or 1
                    _logger.info("WIDTHHH OUTS'%s'", Width_Outs)
                    Width_Outs_split_Dec, Width_Outs_split_Frac = math.modf(Width_Outs)
                    _logger.info("WIDTHHH OUTS SPLITTT DEC'%s'", Width_Outs_split_Dec)
                    _logger.info("WIDTHHH OUTS SPLITTT FRAC'%s'", Width_Outs_split_Frac)
                    Width_Outs_final = math.trunc(Width_Outs_split_Frac)
                    _logger.info("WIDTHHH OUTS FINALLLLL'%s'", Width_Outs_final)
                    Master_Yards = int(customer_qty) / Width_Outs_final
                    _logger.info("MASTTTERRR YARDDSSSS'%s'", Master_Yards)
                    if not Master_Yards.is_integer():
                        Master_Yards = int(Master_Yards) + 1
                    rec.customer_uom_put_up = Master_Yards

                if customer_width != component_width and customer_length == '0.0':
                    _logger.info("CASE22222")
                    Width_Outs = int((component_width - trim_width) / customer_width) or 1
                    _logger.info("WIDTHHH OUTS'%s'", Width_Outs)
                    Width_Outs_split_Dec, Width_Outs_split_Frac = math.modf(Width_Outs)
                    _logger.info("WIDTHHH OUTS SPLITTT DEC'%s'", Width_Outs_split_Dec)
                    _logger.info("WIDTHHH OUTS SPLITTT FRAC'%s'", Width_Outs_split_Frac)
                    Width_Outs_final = math.trunc(Width_Outs_split_Frac)
                    _logger.info("WIDTHHH OUTS FINALLLLL'%s'", Width_Outs_final)
                    Master_Yards = int(customer_qty) / Width_Outs_final
                    _logger.info("MASTTTERRR YARDDSSSS'%s'", Master_Yards)
                    if not Master_Yards.is_integer():
                        Master_Yards = int(Master_Yards) + 1
                    rec.customer_uom_put_up = Master_Yards

                if customer_length != '0.0':
                    _logger.info("CASE333333")
                    _logger.info("Within Elseeee")
                    Width_Outs = int((component_width - trim_width) / customer_width)
                    _logger.info("WIDTHHH OUTS'%s'", Width_Outs)
                    Width_Outs_split_Dec, Width_Outs_split_Frac = math.modf(Width_Outs)
                    _logger.info("WIDTHHH OUTS SPLITTT DEC'%s'", Width_Outs_split_Dec)
                    _logger.info("WIDTHHH OUTS SPLITTT FRAC'%s'", Width_Outs_split_Frac)
                    Width_Outs_final = math.trunc(Width_Outs_split_Frac)
                    _logger.info("WIDTHHH OUTS FINALLLLL LENGTHHH'%s'", Width_Outs_final)
                    counter = 1
                    Length_Outs = (counter * customer_length) + trim_length
                    _logger.info("TRIMMMM LENGTHHHH'%s'", trim_length)
                    _logger.info("LENGTHHH OUTS LENGTHHHH'%s'", Length_Outs)
                    Length_Outs_split_Dec, Length_Outs_split_Frac = math.modf(Length_Outs)
                    Length_Outs_final = math.trunc(Length_Outs_split_Frac)
                    _logger.info("LENGTHHH OUTS FINALLLLL LENGTHHHH'%s'", Length_Outs_final)
                    _logger.info("MACHINEEEEE LENGTHHHH'%s'", machine_length)
                    while Length_Outs_final < machine_length:
                        counter += 1
                        Length_Outs_final = (counter * customer_length) + trim_length
                    Length_Outs_final = counter - 1
                    Master_Sheet_Length = (Length_Outs_final * customer_length) + trim_length
                    machine_stops_ids = self.env['machine.stops'].search(
                        [('x_machine_st', '>=', Master_Sheet_Length)], limit=1
                    )
                    Master_Sheet_Length = machine_stops_ids.x_machine_st
                    _logger.info("MASTTTERRR SHEEET LENGTHHH LENGTHHHH'%s'", Master_Sheet_Length)
                    Master_Outs = (Width_Outs_final * Length_Outs_final) or 1
                    _logger.info("Master_Outs LENGTHHHH'%s'", Master_Outs)
                    Master_Sheets = (int(customer_qty) / Master_Outs)
                    _logger.info("Master_Sheets LENGTHHHH'%s'", Master_Sheets)
                    if not Master_Sheets.is_integer():
                        Master_Sheets = int(Master_Sheets) + 1
                    Master_Yards = int(Master_Sheets * Master_Sheet_Length) / 36
                    if not Master_Yards.is_integer():
                        Master_Yards = int(Master_Yards) + 1
                    rec.customer_uom_put_up = Master_Yards
            else:
                rec.customer_uom_put_up = 0

    # --------------------------
    # CORE SYNC (your previous inverse logic, unchanged)
    # BUT: now it WILL be called from create/write/action_confirm.
    # --------------------------
    def _inverse_x_order_master_yards(self):
        if self.env.context.get('_inverse_yards_running'):
            return
        self = self.with_context(_inverse_yards_running=True)

        _logger.info("Inverse x_order_master_yards for %s MOs", len(self))
        for production in self:
            target_qty = production.x_order_master_yards or 0
            if not target_qty:
                continue

            bom = production.bom_id
            bom_base_qty = bom.product_qty if bom and bom.product_qty else 1.0

            # 1) Update WO output qty
            production.workorder_ids.write({'qty_output_wo': target_qty})
            _logger.info("[MO %s] workorders updated to qty_output_wo=%s", production.name, target_qty)

            # 2) Update component moves on the MO using factor
            comp_moves = production.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
            for mv in comp_moves:
                if mv.bom_line_id and bom_base_qty:
                    factor = mv.bom_line_id.product_qty / bom_base_qty
                else:
                    factor = 1.0  # manually added move — use full master yards
                mv.write({'product_uom_qty': target_qty * factor})
            _logger.info(
                "[MO %s] component moves updated with factor-based qty (count=%s)",
                production.name, len(comp_moves)
            )

            # 3) Sync picking moves (if any) linked to this MO by product
            comp_products = comp_moves.mapped('product_id')
            picking_moves = production.picking_ids.mapped('move_ids_without_package').filtered(
                lambda m: m.state not in ('done', 'cancel') and m.product_id in comp_products
            )
            if picking_moves:
                # Build qty lookup from already-updated comp_moves (factor already applied)
                qty_by_product = {}
                for m in comp_moves:
                    qty_by_product[m.product_id.id] = qty_by_product.get(m.product_id.id, 0) + m.product_uom_qty

                for pm in picking_moves:
                    new_qty = qty_by_product.get(pm.product_id.id)
                    if new_qty is not None and pm.product_uom_qty != new_qty:
                        pm.write({'product_uom_qty': new_qty})
                        for move_line in pm.move_line_ids:
                            if move_line.product_uom_qty != new_qty:
                                move_line.product_uom_qty = new_qty
                _logger.info("[MO %s] picking moves synced (count=%s)", production.name, len(picking_moves))

                to_reassign = picking_moves.filtered(lambda m: m.state in ('assigned', 'partially_available'))
                if to_reassign:
                    to_reassign._do_unreserve()
                (picking_moves | comp_moves)._action_assign()
            else:
                to_reassign = comp_moves.filtered(lambda m: m.state in ('assigned', 'partially_available'))
                if to_reassign:
                    to_reassign._do_unreserve()
                comp_moves._action_assign()

            # 4) Update material requests (custom model)
            mrequests = self.env['project.mrequest'].search([('production_id', '=', production.id)])
            if mrequests:
                comp_by_product = {m.product_id.id: m.product_uom_qty for m in comp_moves}
                for req in mrequests:
                    for line in req.mrequest_lines:
                        new_qty = comp_by_product.get(line.product.id)
                        if new_qty is not None and line.quantity != new_qty:
                            line.write({'quantity': new_qty})
                _logger.info("[MO %s] material requests synced (reqs=%s)", production.name, len(mrequests))

            # 5) Final write to persist
            production.write({'move_raw_ids': [(1, m.id, {'product_uom_qty': m.product_uom_qty}) for m in comp_moves]})
            _logger.info("[MO %s] completed inverse update.", production.name)

            # 6) Merge duplicate picking moves AFTER all writes are done
            fresh_picking_moves = production.move_raw_ids.filtered(
                lambda m: m.state not in ('done', 'cancel') and m.picking_id
            )
            self._merge_duplicate_pick_moves(fresh_picking_moves)
    # def _inverse_x_order_master_yards(self):
    #     """Push x_order_master_yards into component moves, WO qty,
    #     related picking moves (if any), and material requests.
    #     """
    #     if self.env.context.get('_inverse_yards_running'):
    #         return
    #     self = self.with_context(_inverse_yards_running=True)

    #     _logger.info("Inverse x_order_master_yards for %s MOs", len(self))
    #     for production in self:
    #         target_qty = production.x_order_master_yards or 0
    #         if not target_qty:
    #             continue

    #         # 1) Update WO output qty
    #         production.workorder_ids.write({'qty_output_wo': target_qty})
    #         _logger.info("[MO %s] workorders updated to qty_output_wo=%s", production.name, target_qty)

    #         # 2) Update component moves on the MO
    #         comp_moves = production.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
    #         for mv in comp_moves:
    #             mv.write({'product_uom_qty': target_qty})
    #         _logger.info(
    #             "[MO %s] component moves updated to product_uom_qty=%s (count=%s)",
    #             production.name, target_qty, len(comp_moves)
    #         )

    #         # 3) Sync picking moves (if any) linked to this MO by product
    #         comp_products = comp_moves.mapped('product_id')
    #         picking_moves = production.picking_ids.mapped('move_ids_without_package').filtered(
    #             lambda m: m.state not in ('done', 'cancel') and m.product_id in comp_products
    #         )
    #         if picking_moves:
    #             # SUM qty for duplicate BOM lines of same product
    #             qty_by_product = {}
    #             for m in comp_moves:
    #                 qty_by_product[m.product_id.id] = qty_by_product.get(m.product_id.id, 0) + m.product_uom_qty

    #             for pm in picking_moves:
    #                 new_qty = qty_by_product.get(pm.product_id.id)
    #                 if new_qty is not None and pm.product_uom_qty != new_qty:
    #                     pm.write({'product_uom_qty': new_qty})
    #                     for move_line in pm.move_line_ids:
    #                         if move_line.product_uom_qty != new_qty:
    #                             move_line.product_uom_qty = new_qty
    #             _logger.info("[MO %s] picking moves synced (count=%s)", production.name, len(picking_moves))

    #             to_reassign = picking_moves.filtered(lambda m: m.state in ('assigned', 'partially_available'))
    #             if to_reassign:
    #                 to_reassign._do_unreserve()
    #             (picking_moves | comp_moves)._action_assign()
    #         else:
    #             to_reassign = comp_moves.filtered(lambda m: m.state in ('assigned', 'partially_available'))
    #             if to_reassign:
    #                 to_reassign._do_unreserve()
    #             comp_moves._action_assign()

    #         # 4) Update material requests (custom model)
    #         mrequests = self.env['project.mrequest'].search([('production_id', '=', production.id)])
    #         if mrequests:
    #             comp_by_product = {m.product_id.id: m.product_uom_qty for m in comp_moves}
    #             for req in mrequests:
    #                 for line in req.mrequest_lines:
    #                     new_qty = comp_by_product.get(line.product.id)
    #                     if new_qty is not None and line.quantity != new_qty:
    #                         line.write({'quantity': new_qty})
    #             _logger.info("[MO %s] material requests synced (reqs=%s)", production.name, len(mrequests))

    #         # 5) Final write to persist
    #         production.write({'move_raw_ids': [(1, m.id, {'product_uom_qty': m.product_uom_qty}) for m in comp_moves]})
    #         _logger.info("[MO %s] completed inverse update.", production.name)

    #         # 6) Merge duplicate picking moves AFTER all writes are done
    #         fresh_picking_moves = production.move_raw_ids.filtered(
    #             lambda m: m.state not in ('done', 'cancel') and m.picking_id
    #         )
    #         self._merge_duplicate_pick_moves(fresh_picking_moves)

    def _merge_duplicate_pick_moves(self, pick_moves):
        """
        Merge stock.moves on pick component pickings where same product+UoM
        appears more than once (caused by duplicate BOM lines).
        Surviving move gets summed qty; duplicates are cancelled and unlinked.
        """
        seen = {}
        to_unlink = self.env['stock.move']

        for move in pick_moves:
            key = (
                move.picking_id.id,
                move.product_id.id,
                move.product_uom.id,
                move.location_id.id,
                move.location_dest_id.id,
            )
            if key not in seen:
                seen[key] = move
            else:
                # Add qty to the surviving move
                seen[key].product_uom_qty += move.product_uom_qty
                # Reassign any move lines to surviving move
                move.move_line_ids.write({'move_id': seen[key].id})
                to_unlink |= move

        if to_unlink:
            _logger.info("Merging %d duplicate pick moves: %s",
                         len(to_unlink), to_unlink.mapped('product_id.name'))
            # Cancel first to avoid constraint issues, then unlink
            to_unlink.write({'state': 'cancel'})
            to_unlink.unlink()
    # def _inverse_x_order_master_yards(self):
    #     """Push x_order_master_yards into component moves, WO qty,
    #     related picking moves (if any), and material requests.
    #     """
    #     _logger.info("Inverse x_order_master_yards for %s MOs", len(self))
    #     for production in self:
    #         target_qty = production.x_order_master_yards or 0
    #         if not target_qty:
    #             continue

    #         # 1) Update WO output qty
    #         production.workorder_ids.write({'qty_output_wo': target_qty})
    #         _logger.info("[MO %s] workorders updated to qty_output_wo=%s", production.name, target_qty)

    #         # 2) Update component moves on the MO
    #         comp_moves = production.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
    #         for mv in comp_moves:
    #             mv.write({'product_uom_qty': target_qty})
    #         _logger.info(
    #             "[MO %s] component moves updated to product_uom_qty=%s (count=%s)",
    #             production.name, target_qty, len(comp_moves)
    #         )

    #         # 3) Sync picking moves (if any) linked to this MO by product
    #         comp_products = comp_moves.mapped('product_id')
    #         picking_moves = production.picking_ids.mapped('move_ids_without_package').filtered(
    #             lambda m: m.state not in ('done', 'cancel') and m.product_id in comp_products
    #         )
    #         if picking_moves:
    #             qty_by_product = {m.product_id.id: m.product_uom_qty for m in comp_moves}
    #             for pm in picking_moves:
    #                 new_qty = qty_by_product.get(pm.product_id.id)
    #                 if new_qty is not None and pm.product_uom_qty != new_qty:
    #                     pm.write({'product_uom_qty': new_qty})
    #                     for move_line in pm.move_line_ids:
    #                         if move_line.product_uom_qty != new_qty:
    #                             move_line.product_uom_qty = new_qty
    #             _logger.info("[MO %s] picking moves synced (count=%s)", production.name, len(picking_moves))

    #             to_reassign = picking_moves.filtered(lambda m: m.state in ('assigned', 'partially_available'))
    #             if to_reassign:
    #                 to_reassign._do_unreserve()
    #             (picking_moves | comp_moves)._action_assign()
    #         else:
    #             to_reassign = comp_moves.filtered(lambda m: m.state in ('assigned', 'partially_available'))
    #             if to_reassign:
    #                 to_reassign._do_unreserve()
    #             comp_moves._action_assign()

    #         # 4) Update material requests (custom model)
    #         mrequests = self.env['project.mrequest'].search([('production_id', '=', production.id)])
    #         if mrequests:
    #             comp_by_product = {m.product_id.id: m.product_uom_qty for m in comp_moves}
    #             for req in mrequests:
    #                 for line in req.mrequest_lines:
    #                     new_qty = comp_by_product.get(line.product.id)
    #                     if new_qty is not None and line.quantity != new_qty:
    #                         line.write({'quantity': new_qty})
    #             _logger.info("[MO %s] material requests synced (reqs=%s)", production.name, len(mrequests))

    #         # 5) Keep your last write (as you had it)
    #         production.write({'move_raw_ids': [(1, m.id, {'product_uom_qty': m.product_uom_qty}) for m in comp_moves]})
    #         _logger.info("[MO %s] completed inverse update.", production.name)

    # --------------------------
    # CREATE: (non-sale/manual MOs) call inverse if x_order_master_yards came in create vals
    # --------------------------
    @api.model_create_multi
    def create(self, vals_list):
        productions = super().create(vals_list)
        for production, vals in zip(productions, vals_list):
            if vals.get('x_order_master_yards'):
                production._inverse_x_order_master_yards()
        return productions

    # --------------------------
    # WRITE: (sale-based MOs) call inverse when x_order_master_yards changes
    # ALSO keep all your "new component moves" logic as-is.
    # --------------------------
    def write(self, vals):
        _logger.info(">>> MRPProduction.write called on %s with vals=%s", self.ids, vals)

        pre_move_ids_by_production = {}
        if 'move_raw_ids' in vals:
            pre_move_ids_by_production = {production.id: set(production.move_raw_ids.ids) for production in self}

        result = super().write(vals)

        if 'x_order_master_yards' in vals:
            self._inverse_x_order_master_yards()

        if pre_move_ids_by_production:
            for production in self:
                pre_move_ids = pre_move_ids_by_production.get(production.id, set())
                new_moves = production.move_raw_ids.filtered(lambda m: m.id not in pre_move_ids)

                if new_moves and production.x_order_master_yards:
                    editable_moves = new_moves.filtered(lambda m: m.state not in ('done', 'cancel'))
                    if editable_moves:
                        bom = production.bom_id
                        bom_base_qty = bom.product_qty if bom and bom.product_qty else 1.0
                        target_qty = production.x_order_master_yards
                        for mv in editable_moves:
                            if mv.bom_line_id and bom_base_qty:
                                factor = mv.bom_line_id.product_qty / bom_base_qty
                            else:
                                factor = 1.0
                            mv.write({'product_uom_qty': target_qty * factor})
                # if new_moves and production.x_order_master_yards:
                #     editable_moves = new_moves.filtered(lambda m: m.state not in ('done', 'cancel'))
                #     if editable_moves:
                #         editable_moves.write({'product_uom_qty': production.x_order_master_yards})

                if new_moves and production.state != 'draft':
                    warehouse = production.picking_type_id.warehouse_id
                    # Find PC operation type
                    pc_picking_type = self.env['stock.picking.type'].search([
                        ('sequence_code', '=', 'PC'),
                        ('warehouse_id', '=', warehouse.id),
                    ], limit=1)
                    
                    moves_to_reassign = new_moves.filtered(
                        lambda m: m.state not in ('done', 'cancel')
                    )
                    
                    if moves_to_reassign and pc_picking_type:
                        # Get first workorder's workcenter location
                        first_wo = production.workorder_ids.sorted('sequence')[:1]
                        target_location = (
                            first_wo.workcenter_id.location_id
                            if first_wo and first_wo.workcenter_id.location_id
                            else pc_picking_type.default_location_dest_id
                        )
                        
                        # Fix operation type, source, destination, group and origin on new moves
                        moves_to_reassign.write({
                            'picking_type_id': pc_picking_type.id,
                            'location_id': pc_picking_type.default_location_src_id.id,
                            'location_dest_id': target_location.id,
                            'group_id': production.procurement_group_id.id,
                            'origin': production.name,
                        })
                        # Unlink from any wrong picking
                        for move in moves_to_reassign:
                            if move.picking_id and move.picking_id.picking_type_id != pc_picking_type:
                                move.write({'picking_id': False})
                        # Assign to correct picking
                        moves_to_reassign.filtered(
                            lambda m: not m.picking_id
                        )._assign_picking()
                    # if moves_to_reassign and pc_picking_type:
                    #     # Get first workorder's workcenter location
                    #     first_wo = production.workorder_ids.sorted('sequence')[:1]
                    #     target_location = (
                    #         first_wo.workcenter_id.location_id
                    #         if first_wo and first_wo.workcenter_id.location_id
                    #         else pc_picking_type.default_location_dest_id
                    #     )
                        
                    #     # Fix operation type, source and destination on new moves
                    #     moves_to_reassign.write({
                    #         'picking_type_id': pc_picking_type.id,
                    #         'location_id': pc_picking_type.default_location_src_id.id,
                    #         'location_dest_id': target_location.id,
                    #     })
                    #     # Unlink from any wrong picking
                    #     for move in moves_to_reassign:
                    #         if move.picking_id and move.picking_id.picking_type_id != pc_picking_type:
                    #             move.write({'picking_id': False})
                    #     # Assign to correct picking
                    #     moves_to_reassign.filtered(
                    #         lambda m: not m.picking_id
                    #     )._assign_picking()

        # REMOVED: the blanket _sync_pick_components_destination_with_first_workorder() call

        return result

    # --------------------------
    # CONFIRM: keep your old logic + ADD robust location_dest_id update on moves + call inverse once
    # --------------------------
    def action_confirm(self):
        res = super().action_confirm()

        for production in self:
            # wo_name sync
            vals = {}
            first_workorder = production.workorder_ids.sorted('sequence')[:1]
            if first_workorder:
                vals['wo_name'] = first_workorder.workcenter_id.name_get()[0][1]
            if vals and production.picking_ids:
                production.picking_ids.write(vals)

            # qty sync
            if production.x_order_master_yards:
                production._inverse_x_order_master_yards()

            # REMOVED: all location_dest_id logic — pickings don't exist yet at this point
            # location is handled by stock.move._action_confirm hook in ef_stock.py

        return res

    def _action_generate_consumption_wizard(self, consumption_issues):
        ctx = self.env.context.copy()
        lines = []
        for order, product_id, consumed_qty, expected_qty in consumption_issues:
            expected_qty_from_moves = 0.0
            moves = order.move_raw_ids.filtered(lambda move: move.product_id == product_id)
            for move in moves:
                expected_qty_from_moves += move.product_uom._compute_quantity(
                    move.product_uom_qty, product_id.uom_id
                )
            if not moves:
                expected_qty_from_moves = expected_qty
            lines.append((0, 0, {
                'mrp_production_id': order.id,
                'product_id': product_id.id,
                'consumption': order.consumption,
                'product_uom_id': product_id.uom_id.id,
                'product_consumed_qty_uom': consumed_qty,
                'product_expected_qty_uom': expected_qty_from_moves,
            }))
        ctx.update({'default_mrp_production_ids': self.ids, 'default_mrp_consumption_warning_line_ids': lines})
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.action_mrp_consumption_warning")
        action['context'] = ctx
        return action

    # --------------------------
    # NOTIFICATIONS / CRON (unchanged from your code)
    # --------------------------
    @api.model
    def _prepare_allowance_notification_body(self, records_with_targets, records_with_maximums=None):
        body_lines = []
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        if records_with_targets:
            body_lines.append('<h4 style="margin:8px 0">Under Produced</h4>')
            body_lines.append('<ul>')
            for production, target_qty in records_with_targets:
                url = '#'
                if production:
                    url = '%s/web#id=%s&model=mrp.production&view_type=form' % (base_url, production.id)
                body_lines.append(
                    '<li>'
                    '<a href="%s">%s</a>: '
                    'Produced <b>%.2f</b> / Minimum <b>%.2f</b> '
                    '(Master Yards: <b>%.2f</b>)'
                    '</li>' % (
                        url,
                        production.display_name,
                        production.qty_produced or 0.0,
                        target_qty or 0.0,
                        production.x_order_master_yards or 0.0,
                    )
                )
            body_lines.append('</ul>')

        if records_with_maximums:
            body_lines.append('<h4 style="margin:8px 0">Over Produced</h4>')
            body_lines.append('<ul>')
            for production, max_qty in records_with_maximums:
                url = '#'
                if production:
                    url = '%s/web#id=%s&model=mrp.production&view_type=form' % (base_url, production.id)
                body_lines.append(
                    '<li>'
                    '<a href="%s">%s</a>: '
                    'Produced <b>%.2f</b> / Maximum <b>%.2f</b> '
                    '(Master Yards: <b>%.2f</b>)'
                    '</li>' % (
                        url,
                        production.display_name,
                        production.qty_produced or 0.0,
                        max_qty or 0.0,
                        production.x_order_master_yards or 0.0,
                    )
                )
            body_lines.append('</ul>')

        if not (records_with_targets or records_with_maximums):
            return '<p>No manufacturing orders breached their thresholds.</p>'

        body_html = (
            '<p>The following manufacturing orders have breached their allowance thresholds:</p>'
            '%s' % ''.join(body_lines)
        )
        return body_html

    @api.model
    def cron_notify_allowance_underproduction(self):
        _logger.info("ALLOWANCE CRON: started")
        companies = self.env['res.company'].sudo().search([])
        Mail = self.env['mail.mail'].sudo()

        for company in companies:
            recipients = company.allowance_notifier_user_ids.filtered(lambda u: u.partner_id.email)
            emails = recipients.mapped('partner_id.email')
            if not emails:
                _logger.info("No recipients for %s, skipping", company.name)
                continue

            productions = self.sudo().search([
                ('company_id', '=', company.id),
                ('state', 'in', ('progress', 'to_close', 'done')),
            ])
            productions = productions.filtered(
                lambda mo: mo.workorder_ids and all(wo.state == 'done' for wo in mo.workorder_ids)
            )

            if not productions:
                continue

            under_alerts = []
            over_alerts = []

            for production in productions:
                master_yards = float(production.x_order_master_yards or 0.0)
                if master_yards <= 0.0:
                    continue

                try:
                    under_pct = float(str(production.x_order_mrp_under or '0').replace('%', '').strip())
                except ValueError:
                    under_pct = 0.0
                try:
                    over_pct = float(str(production.x_order_mrp_over or '0').replace('%', '').strip())
                except ValueError:
                    over_pct = 0.0

                minimum_qty = max(master_yards * (1 - under_pct / 100.0), 0.0)
                maximum_qty = max(master_yards * (1 + over_pct / 100.0), 0.0)
                produced = float(production.qty_produced or 0.0)

                is_under_allowance = produced < minimum_qty
                is_over_allowance = produced > maximum_qty

                if is_under_allowance:
                    under_alerts.append((production, minimum_qty))
                if is_over_allowance:
                    over_alerts.append((production, maximum_qty))

                update_vals = {}
                if production.under_allowance != is_under_allowance:
                    update_vals['under_allowance'] = is_under_allowance
                if production.over_allowance != is_over_allowance:
                    update_vals['over_allowance'] = is_over_allowance

                if update_vals:
                    production.write(update_vals)

            if not under_alerts and not over_alerts:
                continue

            body_html = self._prepare_allowance_notification_body(under_alerts, over_alerts)
            email_to = ','.join(emails)
            mail_values = {
                'subject': 'MOs below/above allowance thresholds - %s' % company.name,
                'body_html': body_html,
                'email_to': email_to,
                'email_from': company.email or self.env.user.email or 'no-reply@%s' % (company.name or 'odoo'),
                'auto_delete': True,
            }
            mail = Mail.create(mail_values)
            mail.send()
            _logger.info(
                "ALLOWANCE CRON: sent mail (id=%s) to %s, under=%s over=%s",
                mail.id, email_to, len(under_alerts), len(over_alerts)
            )
