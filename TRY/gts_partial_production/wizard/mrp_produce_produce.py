# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
import math
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
import logging
from odoo.tests import Form

_logger = logging.getLogger(__name__)


class MrpProductProduce(models.TransientModel):
    _name = "mrp.product.produce"
    _description = "Record Production"
    _inherit = ["mrp.abstract.workorder"]

    @api.model
    def default_get(self, fields):
        res = super(MrpProductProduce, self).default_get(fields)
        production = self.env['mrp.production']
        production_id = self.env.context.get('default_production_id') or self.env.context.get('active_id')
        if production_id:
            production = self.env['mrp.production'].browse(production_id)
        if production.exists():
            serial_finished = (production.product_id.tracking == 'serial')
            todo_uom = production.product_uom_id.id
            todo_quantity = self._get_todo(production)
            customer_qty = self._get_customer_qty(production)
            if serial_finished:
                # todo_quantity = 1.0
                if production.product_uom_id.uom_type != 'reference':
                    todo_uom = self.env['uom.uom'].search([('category_id', '=', production.product_uom_id.category_id.id), ('uom_type', '=', 'reference')]).id
            if 'production_id' in fields:
                res['production_id'] = production.id
            if 'product_id' in fields:
                res['product_id'] = production.product_id.id
            if 'product_uom_id' in fields:
                res['product_uom_id'] = todo_uom
            if 'serial' in fields:
                res['serial'] = bool(serial_finished)
            if 'qty_producing' in fields:
                res['qty_producing'] = todo_quantity
            if 'consumption' in fields:
                res['consumption'] = production.bom_id.consumption
            res['customer_qty'] = customer_qty
        return res

    serial = fields.Boolean('Requires Serial')
    product_tracking = fields.Selection(related="product_id.tracking")
    is_pending_production = fields.Boolean(compute='_compute_pending_production')

    move_raw_ids = fields.One2many(related='production_id.move_raw_ids', string="PO Components")
    move_finished_ids = fields.One2many(related='production_id.move_finished_ids')

    raw_workorder_line_ids = fields.One2many('mrp.product.produce.line',
        'raw_product_produce_id', string='Components')
    finished_workorder_line_ids = fields.One2many('mrp.product.produce.line',
        'finished_product_produce_id', string='By-products')
    production_id = fields.Many2one('mrp.production', 'Manufacturing Order',
        required=True, ondelete='cascade')
    customer_qty = fields.Float("Customer Qty")
    put_up_rolls = fields.Float(related="production_id.put_up_rolls", string="Put Up(Rolls)")
    uom_put_up = fields.Float(related="production_id.uom_put_up", string="Put up")
    put_up_uom_name = fields.Char(related="production_id.put_up_uom_name")
    outs = fields.Float(related="production_id.outs", string="Outs")
    put_up_size = fields.Float(related="production_id.put_up_size", string="Put up size")

    @api.depends('qty_producing')
    def _compute_pending_production(self):
        """ Compute if it exits remaining quantity once the quantity on the
        current wizard will be processed. The purpose is to display or not
        button 'continue'.
        """
        for product_produce in self:
            remaining_qty = product_produce._get_todo(product_produce.production_id)
            product_produce.is_pending_production = remaining_qty - product_produce.qty_producing > 0.0

    def continue_production(self):
        """ Save current wizard and directly opens a new. """
        self.ensure_one()
        self._record_production()
        action = self.production_id.open_produce_product()
        action['context'] = {'default_production_id': self.production_id.id}
        return action

    def action_generate_serial(self):
        self.ensure_one()
        product_produce_wiz = self.env.ref('gts_partial_production.view_mrp_product_produce_wizard', False)
        self.finished_lot_id = self.env['stock.production.lot'].create({
            'product_id': self.product_id.id,
            'company_id': self.production_id.company_id.id,
            'name': f"{self.production_id.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}"
        })
        return {
            'name': _('Produce'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.product.produce',
            'res_id': self.id,
            'view_id': product_produce_wiz.id,
            'target': 'new',
        }

    def do_produce(self):
        """ Save the current wizard and go back to the MO. """
        self.ensure_one()
        self._record_production()
        self._check_company()
        quantity = self.qty_producing
        if float_compare(quantity, 0, precision_rounding=self.product_uom_id.rounding) <= 0:
            raise UserError(_('You should at least produce some quantity'))
        remaining_quantity = self.production_id.qty_producing - self.production_id.qty_produced
        # updating produced quantity
        for workorder in self.production_id.workorder_ids:
            if self.product_id.tracking == 'serial':
                workorder.qty_produced = workorder.qty_produced + quantity
                # workorder.product_qty = workorder.qty_produced
            else:
                workorder.qty_produced = workorder.qty_produced + quantity
                workorder.qty_producing = workorder.qty_production - workorder.qty_produced
                # workorder.product_qty = workorder.qty_produced
        self.production_id.partial_qty_produced = True
        all_moves = self.env['stock.move'].search(['|', ('raw_material_production_id', '=', self.production_id.id), ('production_id', '=', self.production_id.id)])
        all_moves.filtered(lambda m: m.state == 'confirmed')._action_done()
        # self.production_id.generate_finish_move_line()
        # Update the producing qty
        self.production_id.qty_producing = self.production_id.qty_produced
        return {'type': 'ir.actions.act_window_close'}

    def _get_todo(self, production):
        """ This method will return remaining todo quantity of production. """
        main_product_moves = production.move_finished_ids.filtered(lambda x: x.product_id.id == production.product_id.id)
        to_produce = sum(production.workorder_ids.filtered(lambda r: r.show_partial_produce).final_roll_line_ids.mapped("yards_qty"))
        # Non-yield MO (no final roll lines): fallback to qty_producing set by user on MO
        if not to_produce:
            return production.qty_producing or 0.0
        todo_quantity = to_produce - sum(main_product_moves.mapped('quantity_done'))
        return todo_quantity

    def _get_customer_qty(self, production):
        main_product_moves = production.move_finished_ids.filtered(
            lambda x: x.product_id.id == production.product_id.id)
        customer_qty = sum(
            production.workorder_ids.filtered(lambda r: r.show_partial_produce).final_roll_line_ids.mapped("total_qty"))
        lots = main_product_moves.move_line_ids.mapped('lot_id')
        ex_customer_qty = 0
        if lots:
            ex_customer_qty = sum(lots.mapped('customer_qty'))
        customer_qty = customer_qty - ex_customer_qty
        return customer_qty

    def _record_production(self):
        # Check all the product_produce line have a move id (the user can add product
        # to consume directly in the wizard)
        _logger.info("RECORRDD PRODUCTION\n \n")
        for line in self._workorder_line_ids():
            if not line.move_id:
                # Find move_id that would match
                if line.raw_product_produce_id:
                    moves = line.raw_product_produce_id.move_raw_ids
                else:
                    moves = line.finished_product_produce_id.move_finished_ids
                move_id = moves.filtered(lambda m: m.product_id == line.product_id and m.state not in ('done', 'cancel'))
                if not move_id:
                    # create a move to assign it to the line
                    production = line._get_production()
                    if line.raw_product_produce_id:
                        _logger.info("INSIDDDEE IFF")
                        values = {
                            'name': production.name,
                            'reference': production.name,
                            'product_id': line.product_id.id,
                            'product_uom': line.product_uom_id.id,
                            'location_id': production.location_src_id.id,
                            'location_dest_id': self.product_id.property_stock_production.id,
                            'raw_material_production_id': production.id,
                            'group_id': production.procurement_group_id.id,
                            'origin': production.name,
                            'state': 'confirmed',
                            'company_id': production.company_id.id,
                        }
                    else:
                        _logger.info("INSIDDDEE ELSSEEEE")                       
                        values = production._get_finished_move_value(line.product_id.id, 0, line.product_uom_id.id)
                    move_id = self.env['stock.move'].create(values)
                line.move_id = move_id.id

        # because of an ORM limitation (fields on transient models are not
        # recomputed by updates in non-transient models), the related fields on
        # this model are not recomputed by the creations above
        self.invalidate_cache(['move_raw_ids', 'move_finished_ids'])

        # Save product produce lines data into stock moves/move lines
        for wizard in self:
            quantity = wizard.qty_producing
            if float_compare(quantity, 0, precision_rounding=self.product_uom_id.rounding) <= 0:
                raise UserError(_("The production order for '%s' has no quantity specified.") % self.product_id.display_name)
            quantity = wizard.product_uom_id._compute_quantity(quantity, wizard.production_id.product_uom_id)
            if float_compare(quantity, wizard.production_id.product_qty, precision_rounding=self.product_uom_id.rounding) > 0:
                wizard.production_id.write({'product_qty': quantity})
        self._update_finished_move()
        self._update_moves()
        self.production_id.filtered(lambda mo: mo.state == 'confirmed').write({
            'date_start': datetime.now()
        })
        has_yield = any(wo.final_roll_line_ids for wo in self.production_id.workorder_ids)
        if not has_yield:
            # Non-yield MO (chemicals etc): nothing to regenerate, qty already set via _update_finished_move
            pass
        elif not self.production_id.skip_split:
            self.re_generate_putup_move_line()
        else:
            _logger.info("Cust qty'%s'",self.customer_qty)
            _logger.info("Cust lot qty'%s'",self.finished_lot_id.customer_qty)
            self.finished_lot_id.customer_qty = self.customer_qty
        for mv_line in self.production_id.move_finished_ids:
            if mv_line.state == 'partially_available':
                mv_line._action_done()

    def re_generate_putup_move_line(self):
        self.ensure_one()
        mo = self.production_id

        if not mo.uom_put_up:
            raise UserError(_('Please define Put up detail.'))
        if not mo.outs:
            raise UserError(_('Please define Outs detail.'))

        if (mo.customer_uom_put_up or 0.0) <= 0:
            return

        finished_moves = mo.move_finished_ids.filtered(
            lambda m: m.product_id == self.product_id and m.state not in ('done', 'cancel')
        )
        if not finished_moves:
            return

        # ============================================================
        # DYNAMIC PUT-UPS — one move line per final roll line, qty as-is
        # ============================================================
        if mo.x_dynamic_putup:
            wo = mo.workorder_ids.filtered(lambda w: w.final_roll_line_ids)[:1]
            if not wo:
                raise UserError(_("No workorder found for dynamic put-up lines."))
            if not wo.final_roll_line_ids:
                raise UserError(_("No Final Roll lines found on the workorder."))

            # Incremental: figure out which lines are new since last produce
            already_done_qty = sum(
                finished_moves.mapped('move_line_ids').filtered(
                    lambda ml: ml.state == 'done'
                ).mapped('qty_done')
            )
            cumulative = 0.0
            new_lines = self.env['final.wo.roll']
            for line in wo.final_roll_line_ids.sorted('id'):
                if cumulative >= already_done_qty:
                    new_lines |= line
                else:
                    cumulative += line.yards_qty

            if not new_lines:
                return

            created_lines = self.env['stock.move.line']
            for move in finished_moves:
                if not move.move_line_ids:
                    raise UserError(_('No existing move line found to use as a template.'))
                template_ml = move.move_line_ids[0]
                lot_required = (template_ml.product_id.tracking == 'lot')

                cmds = [(5, 0, 0)]
                for roll_line in new_lines:
                    qty = roll_line.yards_qty
                    if not qty or qty <= 0:
                        continue
                    lot_id = False
                    if lot_required:
                        lot = self.env['stock.production.lot'].create({
                            'product_id': template_ml.product_id.id,
                            'company_id': template_ml.company_id.id,
                            'name': f"{mo.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}",
                        })
                        lot.customer_qty = roll_line.total_qty
                        lot_id = lot.id
                    cmds.append((0, 0, {
                        'move_id': move.id,
                        'company_id': template_ml.company_id.id,
                        'product_id': template_ml.product_id.id,
                        'product_uom_id': template_ml.product_uom_id.id,
                        'location_id': template_ml.location_id.id,
                        'location_dest_id': template_ml.location_dest_id.id,
                        'qty_done': qty,
                        'product_uom_qty': qty,
                        'lot_id': lot_id,
                    }))

                move.write({'move_line_ids': cmds})
                created_lines |= move.move_line_ids
                done_sum = sum(move.move_line_ids.mapped('qty_done'))
                move.write({'product_uom_qty': done_sum})

            # Sync delivery picking (same pattern as existing blocks)
            sale_orders = mo.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
            if not sale_orders:
                return
            sale_order = sale_orders[0]
            picking = sale_order.picking_ids.filtered(lambda p: p.location_id.id == mo.location_dest_id.id)
            if not picking or len(picking) != 1:
                return
            picking = picking[0]
            pick_move = picking.move_ids_without_package.filtered(lambda m: m.product_id == self.product_id)
            if not pick_move:
                return
            pick_move = pick_move[0]

            new_total = sum(created_lines.mapped('qty_done')) or 0.0
            if new_total <= 0:
                return

            pick_move.write({'product_uom_qty': new_total})
            if picking.state not in ('done', 'cancel'):
                if hasattr(pick_move, '_do_unreserve'):
                    pick_move._do_unreserve()
                elif hasattr(pick_move, 'do_unreserve'):
                    pick_move.do_unreserve()

            pick_cmds = [(5, 0, 0)]
            for ml in created_lines:
                pick_cmds.append((0, 0, {
                    'picking_id': picking.id,
                    'move_id': pick_move.id,
                    'company_id': picking.company_id.id,
                    'product_id': ml.product_id.id,
                    'product_uom_id': ml.product_uom_id.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'qty_done': ml.qty_done,
                    'lot_id': ml.lot_id.id or False,
                }))
            picking.write({'move_line_ids_without_package': pick_cmds})
            return

        # ============================================================
        # MULTI-SLIT (CLIENT FORMULA)
        # ============================================================
        if mo.x_mrp_order_slit:
            slit_lines = mo.x_mrp_order_multi_slit_size
            if not slit_lines:
                raise UserError(_('No slit sizes defined for this multi-slit order.'))

            wo = getattr(self, "workorder_id", False) or False
            if not wo:
                wo = mo.workorder_ids.filtered(lambda w: w.final_roll_line_ids)[:1]
            if not wo:
                raise UserError(_("No workorder found to read consumed master yards."))

            if not wo.final_roll_line_ids:
                raise UserError(_("No Final Roll lines found on the workorder to read consumed_qty."))

            consumed_master_yds = sum(wo.final_roll_line_ids.mapped('consumed_qty') or [])
            if not consumed_master_yds or consumed_master_yds <= 0:
                raise UserError(_("Consumed master yards is 0. Please check consumed_qty on Final Roll lines."))

            master_width = self.product_id.x_item_width or 0.0
            if master_width <= 0:
                raise UserError(_('Master width (x_item_width) is missing on the product.'))

            k = consumed_master_yds / master_width

            total_slit_width = sum(
                (l.x_order_mrp_size or 0.0) * int(l.x_order_mrp_outs or 0)
                for l in slit_lines
            )
            waste_inches = master_width - total_slit_width
            if waste_inches < 0:
                raise UserError(_('Total slit width exceeds master width. Please check slit sizes.'))

            total_outs = sum(int(l.x_order_mrp_outs or 0) for l in slit_lines)
            if total_outs <= 0:
                raise UserError(_('Total outs must be greater than zero.'))

            waste_share = (waste_inches * k) / total_outs

            slit_putup_yds = mo.uom_put_up
            created_lines = self.env['stock.move.line']

            for move in finished_moves:
                if not move.move_line_ids:
                    raise UserError(_('No existing move line found to use as a template.'))

                template_ml = move.move_line_ids[0]
                lot_required = (template_ml.product_id.tracking == 'lot')

                cmds = [(5, 0, 0)]

                for s in slit_lines:
                    width_in = s.x_order_mrp_size or 0.0
                    s_outs = int(s.x_order_mrp_outs or 0)
                    if width_in <= 0 or s_outs <= 0:
                        continue

                    equiv_master_yds = math.ceil((k * width_in) + waste_share)

                    for i in range(s_outs):
                        lot_id = False
                        if lot_required:
                            lot = self.env['stock.production.lot'].create({
                                'product_id': template_ml.product_id.id,
                                'company_id': template_ml.company_id.id,
                                'name': f"{mo.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}",
                            })
                            lot.customer_qty = slit_putup_yds
                            lot_id = lot.id

                        cmds.append((0, 0, {
                            'move_id': move.id,
                            'company_id': template_ml.company_id.id,
                            'product_id': template_ml.product_id.id,
                            'product_uom_id': template_ml.product_uom_id.id,
                            'location_id': template_ml.location_id.id,
                            'location_dest_id': template_ml.location_dest_id.id,
                            'qty_done': equiv_master_yds,
                            'product_uom_qty': equiv_master_yds,
                            'lot_id': lot_id,
                        }))

                move.write({'move_line_ids': cmds})
                created_lines |= move.move_line_ids

                # keep your critical fix
                done_sum = sum(move.move_line_ids.mapped('qty_done'))
                move.write({'product_uom_qty': done_sum})

            # ---- Sync delivery picking detailed ops (fixed) ----
            sale_orders = mo.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
            if not sale_orders:
                return
            sale_order = sale_orders[0]

            picking = sale_order.picking_ids.filtered(lambda p: p.location_id.id == mo.location_dest_id.id)
            if not picking or len(picking) != 1:
                return
            picking = picking[0]

            pick_move = picking.move_ids_without_package.filtered(lambda m: m.product_id == self.product_id)
            if not pick_move:
                return
            pick_move = pick_move[0]

            new_total = sum(created_lines.mapped('qty_done')) or 0.0
            if new_total <= 0:
                return

            # 1) Align delivery demand FIRST (important for clean unreserve/reconcile)
            pick_move.write({'product_uom_qty': new_total})

            # 2) Unreserve on the move (Odoo 14) if applicable
            if picking.state not in ('done', 'cancel'):
                if hasattr(pick_move, '_do_unreserve'):
                    pick_move._do_unreserve()
                elif hasattr(pick_move, 'do_unreserve'):
                    pick_move.do_unreserve()

            # 3) Rebuild delivery detailed ops:
            #    IMPORTANT: Do NOT set product_uom_qty on move lines (reserved qty) -> it causes the unreserve error later.
            pick_cmds = [(5, 0, 0)]
            for ml in created_lines:
                pick_cmds.append((0, 0, {
                    'picking_id': picking.id,
                    'move_id': pick_move.id,
                    'company_id': picking.company_id.id,
                    'product_id': ml.product_id.id,
                    'product_uom_id': ml.product_uom_id.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'qty_done': ml.qty_done,
                    'lot_id': ml.lot_id.id or False,
                }))
            picking.write({'move_line_ids_without_package': pick_cmds})

            # 4) Do NOT call action_assign() here.
            #    It can recreate reservations/lines and bring back the conflict.
            return

        # ============================================================
        # NON-SLIT (unchanged)
        # ============================================================
        for move in finished_moves:
            if not move.move_line_ids:
                raise UserError(_('No existing move line found to use as a template.'))

            template_ml = move.move_line_ids[0]
            lot_required = (template_ml.product_id.tracking == 'lot')

            customer_qty = self.customer_qty or 0.0
            putup = mo.uom_put_up or 0.0
            outs = mo.outs or 0.0

            rolls = int(customer_qty / putup) if putup else 0

            m_yard_per_roll = math.ceil(putup / outs) if outs else 0.0
            total_yards = rolls * putup
            remaining_yards = customer_qty - total_yards

            cmds = [(5, 0, 0)]

            def _new_lot():
                return self.env['stock.production.lot'].create({
                    'product_id': template_ml.product_id.id,
                    'company_id': template_ml.company_id.id,
                    'name': f"{mo.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}",
                })

            for r in range(rolls):
                lot_id = False
                if lot_required:
                    lot = _new_lot()
                    lot.customer_qty = putup
                    lot_id = lot.id

                cmds.append((0, 0, {
                    'move_id': move.id,
                    'company_id': template_ml.company_id.id,
                    'product_id': template_ml.product_id.id,
                    'product_uom_id': template_ml.product_uom_id.id,
                    'location_id': template_ml.location_id.id,
                    'location_dest_id': template_ml.location_dest_id.id,
                    'product_uom_qty': m_yard_per_roll,
                    'qty_done': m_yard_per_roll,
                    'lot_id': lot_id,
                }))

            if remaining_yards and remaining_yards > 0:
                rem_each = math.ceil(remaining_yards / outs) if outs else 0.0

                lot_id = False
                if lot_required:
                    lot = _new_lot()
                    lot.customer_qty = remaining_yards
                    lot_id = lot.id

                cmds.append((0, 0, {
                    'move_id': move.id,
                    'company_id': template_ml.company_id.id,
                    'product_id': template_ml.product_id.id,
                    'product_uom_id': template_ml.product_uom_id.id,
                    'location_id': template_ml.location_id.id,
                    'location_dest_id': template_ml.location_dest_id.id,
                    'product_uom_qty': rem_each,
                    'qty_done': rem_each,
                    'lot_id': lot_id,
                }))

            move.write({'move_line_ids': cmds})

            done_sum = sum(move.move_line_ids.mapped('qty_done'))
            if done_sum > move.product_uom_qty:
                move.write({'product_uom_qty': done_sum})

            sale_orders = mo.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
            if not sale_orders:
                continue
            sale_order = sale_orders[0]

            picking = sale_order.picking_ids.filtered(lambda p: p.location_id.id == mo.location_dest_id.id)
            if not picking or len(picking) != 1:
                continue
            picking = picking[0]

            pick_move = picking.move_ids_without_package.filtered(lambda m: m.product_id == self.product_id)
            if not pick_move:
                continue
            pick_move = pick_move[0]

            picking.write({'move_line_ids_without_package': [(5, 0, 0)]})

            pick_cmds = [(5, 0, 0)]
            for ml in move.move_line_ids:
                pick_cmds.append((0, 0, {
                    'picking_id': picking.id,
                    'move_id': pick_move.id,
                    'company_id': picking.company_id.id,
                    'product_id': ml.product_id.id,
                    'product_uom_id': ml.product_uom_id.id,
                    'location_id': picking.location_id.id,
                    'location_dest_id': picking.location_dest_id.id,
                    'qty_done': ml.qty_done,
                    'lot_id': ml.lot_id.id or False,
                }))
            picking.write({'move_line_ids_without_package': pick_cmds})




#-----------------------------------FEb 15 night
    # def re_generate_putup_move_line(self):
    #     self.ensure_one()
    #     mo = self.production_id

    #     if not mo.uom_put_up:
    #         raise UserError(_('Please define Put up detail.'))
    #     if not mo.outs:
    #         raise UserError(_('Please define Outs detail.'))

    #     if (mo.customer_uom_put_up or 0.0) <= 0:
    #         return

    #     # Finished product move(s) for this wizard product
    #     finished_moves = mo.move_finished_ids.filtered(
    #         lambda m: m.product_id == self.product_id and m.state not in ('done', 'cancel')
    #     )
    #     if not finished_moves:
    #         return

    #     # ============================================================
    #     # MULTI-SLIT (CLIENT FORMULA) — ONLY WHEN x_mrp_order_slit TRUE
    #     # AND multi slit lines exist. This is your proven working block.
    #     # ============================================================
    #     if mo.x_mrp_order_slit:
    #         slit_lines = mo.x_mrp_order_multi_slit_size
    #         if not slit_lines:
    #             # If slit flag is true but no multi-slit sizes, you can either:
    #             # - raise error (strict) OR
    #             # - fall back to legacy slit math (not requested here)
    #             raise UserError(_('No slit sizes defined for this multi-slit order.'))

    #         # ---- get consumed master yards from WO final_roll_line_ids ----
    #         wo = getattr(self, "workorder_id", False) or False
    #         if not wo:
    #             wo = mo.workorder_ids.filtered(lambda w: w.state in ('progress', 'ready', 'done'))[:1]
    #         if not wo:
    #             raise UserError(_("No workorder found to read consumed master yards."))

    #         if not wo.final_roll_line_ids:
    #             raise UserError(_("No Final Roll lines found on the workorder to read consumed_qty."))

    #         consumed_master_yds = sum(wo.final_roll_line_ids.mapped('consumed_qty') or [])
    #         if not consumed_master_yds or consumed_master_yds <= 0:
    #             raise UserError(_("Consumed master yards is 0. Please check consumed_qty on Final Roll lines."))

    #         master_width = self.product_id.x_item_width or 0.0
    #         if master_width <= 0:
    #             raise UserError(_('Master width (x_item_width) is missing on the product.'))

    #         # ---- client formula precompute ----
    #         k = consumed_master_yds / master_width  # master yards per inch

    #         total_slit_width = sum(
    #             (l.x_order_mrp_size or 0.0) * int(l.x_order_mrp_outs or 0)
    #             for l in slit_lines
    #         )
    #         waste_inches = master_width - total_slit_width
    #         if waste_inches < 0:
    #             raise UserError(_('Total slit width exceeds master width. Please check slit sizes.'))

    #         total_outs = sum(int(l.x_order_mrp_outs or 0) for l in slit_lines)
    #         if total_outs <= 0:
    #             raise UserError(_('Total outs must be greater than zero.'))

    #         waste_share = (waste_inches * k) / total_outs

    #         slit_putup_yds = mo.uom_put_up  # informational slit yards per roll (e.g. 1000)
    #         created_lines = self.env['stock.move.line']

    #         # ---- rebuild finished move lines on MO ----
    #         for move in finished_moves:
    #             if not move.move_line_ids:
    #                 raise UserError(_('No existing move line found to use as a template.'))

    #             template_ml = move.move_line_ids[0]
    #             lot_required = (template_ml.product_id.tracking == 'lot')

    #             cmds = [(5, 0, 0)]  # clear move lines

    #             for s in slit_lines:
    #                 width_in = s.x_order_mrp_size or 0.0
    #                 s_outs = int(s.x_order_mrp_outs or 0)
    #                 if width_in <= 0 or s_outs <= 0:
    #                     continue

    #                 equiv_master_yds = math.ceil((k * width_in) + waste_share)

    #                 for i in range(s_outs):
    #                     lot_id = False
    #                     if lot_required:
    #                         lot = self.env['stock.production.lot'].create({
    #                             'product_id': template_ml.product_id.id,
    #                             'company_id': template_ml.company_id.id,
    #                             'name': f"{mo.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}",
    #                         })
    #                         lot.customer_qty = slit_putup_yds  # keep 1000 as info
    #                         lot_id = lot.id

    #                     cmds.append((0, 0, {
    #                         'move_id': move.id,
    #                         'company_id': template_ml.company_id.id,
    #                         'product_id': template_ml.product_id.id,
    #                         'product_uom_id': template_ml.product_uom_id.id,
    #                         'location_id': template_ml.location_id.id,
    #                         'location_dest_id': template_ml.location_dest_id.id,
    #                         'qty_done': equiv_master_yds,
    #                         'product_uom_qty': equiv_master_yds,
    #                         'lot_id': lot_id,
    #                     }))

    #             move.write({'move_line_ids': cmds})
    #             created_lines |= move.move_line_ids

    #             # ✅ CRITICAL FIX:
    #             # For multi-slit, ALWAYS sync demand to the generated total
    #             # (otherwise Odoo may reconcile back to old demand like 1000 later)
    #             done_sum = sum(move.move_line_ids.mapped('qty_done'))
    #             move.write({'product_uom_qty': done_sum})

    #         # ---- Sync delivery picking detailed ops (force rebuild) ----
    #         sale_orders = mo.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
    #         if not sale_orders:
    #             return
    #         sale_order = sale_orders[0]

    #         picking = sale_order.picking_ids.filtered(lambda p: p.location_id.id == mo.location_dest_id.id)
    #         if not picking or len(picking) != 1:
    #             return
    #         picking = picking[0]

    #         pick_move = picking.move_ids_without_package.filtered(lambda m: m.product_id == self.product_id)
    #         if not pick_move:
    #             return
    #         pick_move = pick_move[0]

    #         if picking.state not in ('done', 'cancel'):
    #             if hasattr(pick_move, '_do_unreserve'):
    #                 pick_move._do_unreserve()
    #             elif hasattr(pick_move, 'do_unreserve'):
    #                 pick_move.do_unreserve()

    #         new_total = sum(created_lines.mapped('qty_done')) or 0.0
    #         if new_total <= 0:
    #             return

    #         pick_move.write({'product_uom_qty': new_total})

    #         pick_cmds = [(5, 0, 0)]
    #         for ml in created_lines:
    #             pick_cmds.append((0, 0, {
    #                 'picking_id': picking.id,
    #                 'move_id': pick_move.id,
    #                 'company_id': picking.company_id.id,
    #                 'product_id': ml.product_id.id,
    #                 'product_uom_id': ml.product_uom_id.id,
    #                 'location_id': picking.location_id.id,
    #                 'location_dest_id': picking.location_dest_id.id,
    #                 'qty_done': ml.qty_done,
    #                 'product_uom_qty': ml.product_uom_qty,
    #                 'lot_id': ml.lot_id.id or False,
    #             }))
    #         picking.write({'move_line_ids_without_package': pick_cmds})

    #         if picking.state not in ('done', 'cancel'):
    #             picking.action_assign()

    #         return

    #     # ============================================================
    #     # NON-SLIT (STABLE OLD) — this is your proven working block
    #     # ============================================================
    #     for move in finished_moves:
    #         if not move.move_line_ids:
    #             raise UserError(_('No existing move line found to use as a template.'))

    #         template_ml = move.move_line_ids[0]
    #         lot_required = (template_ml.product_id.tracking == 'lot')

    #         customer_qty = self.customer_qty or 0.0
    #         putup = mo.uom_put_up or 0.0
    #         outs = mo.outs or 0.0

    #         rolls = int(customer_qty / putup) if putup else 0

    #         m_yard_per_roll = math.ceil(putup / outs) if outs else 0.0
    #         total_yards = rolls * putup
    #         remaining_yards = customer_qty - total_yards

    #         cmds = [(5, 0, 0)]  # clear existing move lines

    #         def _new_lot():
    #             return self.env['stock.production.lot'].create({
    #                 'product_id': template_ml.product_id.id,
    #                 'company_id': template_ml.company_id.id,
    #                 'name': f"{mo.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}",
    #             })

    #         for r in range(rolls):
    #             lot_id = False
    #             if lot_required:
    #                 lot = _new_lot()
    #                 lot.customer_qty = putup
    #                 lot_id = lot.id

    #             cmds.append((0, 0, {
    #                 'move_id': move.id,
    #                 'company_id': template_ml.company_id.id,
    #                 'product_id': template_ml.product_id.id,
    #                 'product_uom_id': template_ml.product_uom_id.id,
    #                 'location_id': template_ml.location_id.id,
    #                 'location_dest_id': template_ml.location_dest_id.id,
    #                 'product_uom_qty': m_yard_per_roll,
    #                 'qty_done': m_yard_per_roll,
    #                 'lot_id': lot_id,
    #             }))

    #         if remaining_yards and remaining_yards > 0:
    #             rem_each = math.ceil(remaining_yards / outs) if outs else 0.0

    #             lot_id = False
    #             if lot_required:
    #                 lot = _new_lot()
    #                 lot.customer_qty = remaining_yards
    #                 lot_id = lot.id

    #             cmds.append((0, 0, {
    #                 'move_id': move.id,
    #                 'company_id': template_ml.company_id.id,
    #                 'product_id': template_ml.product_id.id,
    #                 'product_uom_id': template_ml.product_uom_id.id,
    #                 'location_id': template_ml.location_id.id,
    #                 'location_dest_id': template_ml.location_dest_id.id,
    #                 'product_uom_qty': rem_each,
    #                 'qty_done': rem_each,
    #                 'lot_id': lot_id,
    #             }))

    #         move.write({'move_line_ids': cmds})

    #         # keep old intent: only increase move demand if producing more
    #         done_sum = sum(move.move_line_ids.mapped('qty_done'))
    #         if done_sum > move.product_uom_qty:
    #             move.write({'product_uom_qty': done_sum})

    #         # Sync delivery detailed ops (ALWAYS rebuild)
    #         sale_orders = mo.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
    #         if not sale_orders:
    #             continue
    #         sale_order = sale_orders[0]

    #         picking = sale_order.picking_ids.filtered(lambda p: p.location_id.id == mo.location_dest_id.id)
    #         if not picking or len(picking) != 1:
    #             continue
    #         picking = picking[0]

    #         pick_move = picking.move_ids_without_package.filtered(lambda m: m.product_id == self.product_id)
    #         if not pick_move:
    #             continue
    #         pick_move = pick_move[0]

    #         picking.write({'move_line_ids_without_package': [(5, 0, 0)]})

    #         pick_cmds = [(5, 0, 0)]
    #         for ml in move.move_line_ids:
    #             pick_cmds.append((0, 0, {
    #                 'picking_id': picking.id,
    #                 'move_id': pick_move.id,
    #                 'company_id': picking.company_id.id,
    #                 'product_id': ml.product_id.id,
    #                 'product_uom_id': ml.product_uom_id.id,
    #                 'location_id': picking.location_id.id,
    #                 'location_dest_id': picking.location_dest_id.id,
    #                 'qty_done': ml.qty_done,
    #                 'lot_id': ml.lot_id.id or False,
    #             }))
    #         picking.write({'move_line_ids_without_package': pick_cmds})


#----------------------------------------before Feb15
    # def re_generate_putup_move_line(self):
    #     self.ensure_one()
    #     mo = self.production_id

    #     if not mo.uom_put_up:
    #         raise UserError(_('Please define Put up detail.'))
    #     if not mo.outs:
    #         raise UserError(_('Please define Outs detail.'))

    #     # ============================================================
    #     # NEW SLIT LOGIC (ONLY WHEN x_mrp_order_slit IS TRUE)
    #     # - builds MO finished move lines based on slit sizes
    #     # - rebuilds delivery detailed ops from those lines
    #     # ============================================================
    #     if mo.x_mrp_order_slit:
    #         # ---- get consumed master yards from WO final_roll_line_ids ----
    #         wo = getattr(self, "workorder_id", False) or False
    #         if not wo:
    #             wo = mo.workorder_ids.filtered(lambda w: w.state in ('progress', 'ready', 'done'))[:1]
    #         if not wo:
    #             raise UserError(_("No workorder found to read consumed master yards."))

    #         if not wo.final_roll_line_ids:
    #             raise UserError(_("No Final Roll lines found on the workorder to read consumed_qty."))

    #         consumed_master_yds = sum(wo.final_roll_line_ids.mapped('consumed_qty') or [])
    #         if not consumed_master_yds or consumed_master_yds <= 0:
    #             raise UserError(_("Consumed master yards is 0. Please check consumed_qty on Final Roll lines."))

    #         master_width = self.product_id.x_item_width or 0.0
    #         if master_width <= 0:
    #             raise UserError(_('Master width (x_item_width) is missing on the product.'))

    #         slit_lines = mo.x_mrp_order_multi_slit_size
    #         if not slit_lines:
    #             raise UserError(_('No slit sizes defined for this multi-slit order.'))

    #         finished_moves = mo.move_finished_ids.filtered(
    #             lambda m: m.product_id == self.product_id and m.state not in ('done', 'cancel')
    #         )
    #         if not finished_moves:
    #             return

    #         # ---- client formula precompute ----
    #         k = consumed_master_yds / master_width  # master yards per inch

    #         total_slit_width = sum(
    #             (l.x_order_mrp_size or 0.0) * int(l.x_order_mrp_outs or 0)
    #             for l in slit_lines
    #         )
    #         waste_inches = master_width - total_slit_width
    #         if waste_inches < 0:
    #             raise UserError(_('Total slit width exceeds master width. Please check slit sizes.'))

    #         total_outs = sum(int(l.x_order_mrp_outs or 0) for l in slit_lines)
    #         if total_outs <= 0:
    #             raise UserError(_('Total outs must be greater than zero.'))

    #         waste_share = (waste_inches * k) / total_outs

    #         slit_putup_yds = mo.uom_put_up  # informational slit yards per roll (e.g. 1000)
    #         created_lines = self.env['stock.move.line']

    #         # ---- rebuild finished move lines on MO ----
    #         for move in finished_moves:
    #             if not move.move_line_ids:
    #                 raise UserError(_('No existing move line found to use as a template.'))

    #             template_ml = move.move_line_ids[0]
    #             lot_required = (template_ml.product_id.tracking == 'lot')

    #             cmds = [(5, 0, 0)]  # clear move lines

    #             for s in slit_lines:
    #                 width_in = s.x_order_mrp_size or 0.0
    #                 outs = int(s.x_order_mrp_outs or 0)
    #                 if width_in <= 0 or outs <= 0:
    #                     continue

    #                 # Equivalent master yards per roll (rounded up)
    #                 equiv_master_yds = math.ceil((k * width_in) + waste_share)

    #                 for i in range(outs):
    #                     lot_id = False
    #                     if lot_required:
    #                         lot = self.env['stock.production.lot'].create({
    #                             'product_id': template_ml.product_id.id,
    #                             'company_id': template_ml.company_id.id,
    #                             'name': f"{mo.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}",
    #                         })
    #                         # keep 1000 as informational slit yards
    #                         lot.customer_qty = slit_putup_yds
    #                         lot_id = lot.id

    #                     vals = {
    #                         'move_id': move.id,
    #                         'company_id': template_ml.company_id.id,
    #                         'product_id': template_ml.product_id.id,
    #                         'product_uom_id': template_ml.product_uom_id.id,
    #                         'location_id': template_ml.location_id.id,
    #                         'location_dest_id': template_ml.location_dest_id.id,

    #                         # Drives ON HAND (Quant): master-equivalent yards
    #                         'qty_done': equiv_master_yds,
    #                         'product_uom_qty': equiv_master_yds,

    #                         'lot_id': lot_id,
    #                     }
    #                     cmds.append((0, 0, vals))

    #             move.write({'move_line_ids': cmds})
    #             created_lines |= move.move_line_ids

    #             done_sum = sum(move.move_line_ids.mapped('qty_done'))
    #             if done_sum > move.product_uom_qty:
    #                 move.write({'product_uom_qty': done_sum})

    #         # ---- Sync delivery picking detailed ops (force rebuild) ----
    #         sale_orders = mo.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
    #         if not sale_orders:
    #             return
    #         sale_order = sale_orders[0]

    #         picking = sale_order.picking_ids.filtered(lambda p: p.location_id.id == mo.location_dest_id.id)
    #         if not picking or len(picking) != 1:
    #             return
    #         picking = picking[0]

    #         pick_move = picking.move_ids_without_package.filtered(lambda m: m.product_id == self.product_id)
    #         if not pick_move:
    #             return
    #         pick_move = pick_move[0]

    #         # Clear any existing reservations first (prevents unreserve errors)
    #         if picking.state not in ('done', 'cancel'):
    #             picking.action_unreserve()

    #         new_total = sum(created_lines.mapped('qty_done')) or 0.0
    #         if new_total <= 0:
    #             return

    #         # align demand with new master-equivalent totals
    #         pick_move.write({'product_uom_qty': new_total})

    #         pick_cmds = [(5, 0, 0)]
    #         for ml in created_lines:
    #             pick_cmds.append((0, 0, {
    #                 'picking_id': picking.id,
    #                 'move_id': pick_move.id,
    #                 'company_id': picking.company_id.id,
    #                 'product_id': ml.product_id.id,
    #                 'product_uom_id': ml.product_uom_id.id,
    #                 'location_id': picking.location_id.id,
    #                 'location_dest_id': picking.location_dest_id.id,
    #                 'qty_done': ml.qty_done,
    #                 'product_uom_qty': ml.product_uom_qty,
    #                 'lot_id': ml.lot_id.id or False,
    #             }))
    #         picking.write({'move_line_ids_without_package': pick_cmds})

    #         if picking.state not in ('done', 'cancel'):
    #             picking.action_assign()

    #         return

    #     # ============================================================
    #     # OLD LOGIC (runs when x_mrp_order_slit is FALSE)
    #     # - keeps your existing behavior but ALWAYS rebuilds
    #     #   delivery detailed ops from produced lots
    #     # ============================================================
    #     customer_uom_put_up = mo.customer_uom_put_up
    #     remaining_yards = 0.0

    #     if customer_uom_put_up > 0:
    #         production_move = mo.move_finished_ids.filtered(
    #             lambda move: move.product_id == self.product_id and move.state not in ('done', 'cancel')
    #         )

    #         for pro_mv in production_move:
    #             mv_data = []
    #             for mv_line in pro_mv.move_line_ids:
    #                 mv_data.append((2, mv_line.id))
    #                 lot_required = True if mv_line.product_id.tracking == 'lot' else False

    #                 rolls = int((self.customer_qty or 0.0) / mo.uom_put_up)
    #                 total_yards = rolls * mo.uom_put_up
    #                 remaining_yards = (self.customer_qty or 0.0) - total_yards

    #                 m_yard_per_roll = math.ceil(mo.uom_put_up / mo.outs)

    #                 lot_rec = mv_line.lot_id or False
    #                 for _x in range(0, rolls):
    #                     if lot_required:
    #                         if not lot_rec:
    #                             lot_rec = self.env['stock.production.lot'].create({
    #                                 'product_id': mv_line.product_id.id,
    #                                 'company_id': mv_line.company_id.id,
    #                                 'name': f"{mo.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}"
    #                             })
    #                         else:
    #                             lot_rec.product_qty = 0

    #                         mv_line.copy(default={
    #                             'product_uom_qty': m_yard_per_roll,
    #                             'qty_done': m_yard_per_roll,
    #                             'lot_id': lot_rec.id if lot_rec else False
    #                         })
    #                         lot_rec.customer_qty = mo.uom_put_up
    #                         lot_rec = False

    #                 if remaining_yards:
    #                     if lot_required:
    #                         new_rem_lot_rec = self.env['stock.production.lot'].create({
    #                             'product_id': mv_line.product_id.id,
    #                             'company_id': mv_line.company_id.id,
    #                             'name': f"{mo.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}"
    #                         })
    #                         mv_line.copy(default={
    #                             'product_uom_qty': math.ceil(remaining_yards / mo.outs),
    #                             'qty_done': math.ceil(remaining_yards / mo.outs),
    #                             'lot_id': new_rem_lot_rec.id if new_rem_lot_rec else False
    #                         })
    #                         new_rem_lot_rec.customer_qty = remaining_yards

    #             pro_mv.move_line_ids = mv_data

    #             if sum(pro_mv.move_line_ids.mapped('qty_done')) > pro_mv.product_uom_qty:
    #                 production_move.write({"product_uom_qty": sum(pro_mv.move_line_ids.mapped('qty_done'))})

    #             # ALWAYS rebuild delivery detailed ops from produced move lines
    #             sale_order_ids = mo.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
    #             if sale_order_ids:
    #                 sale_order_id = sale_order_ids[0]
    #                 picking_rec = sale_order_id.picking_ids.filtered(
    #                     lambda m: m.location_id.id == mo.location_dest_id.id
    #                 )
    #                 if picking_rec and len(picking_rec) == 1:
    #                     picking = picking_rec[0]

    #                     # clear existing detailed ops and refill
    #                     picking.move_line_ids_without_package = [(5, 0, 0)]

    #                     picking_form = Form(picking)
    #                     for mv_line_rec in pro_mv.move_line_ids:
    #                         with picking_form.move_line_ids_without_package.new() as new_move:
    #                             new_move.product_id = mv_line_rec.product_id
    #                             new_move.lot_id = mv_line_rec.lot_id
    #                             new_move.qty_done = mv_line_rec.qty_done
    #                     picking_form.save()


            # for pro_mv in production_move:
            #     for mv_line in pro_mv.move_line_ids:
            #         print (mv_line, mv_line.qty_done)
                    # # Remaining
                    # if remaining_yards:
                    #     # 1 rolls deserve
                    #     print("\n\n\n XXXXXXXXXXx", remaining_yards)
                    #     new_rem_lot_rec = self.env['stock.production.lot'].create({
                    #         'product_id': mv_line.product_id.id,
                    #         'company_id': mv_line.company_id.id,
                    #         'name': f"{self.production_id.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}"
                    #     })
                    #     new_mv_rec = mv_line.copy(
                    #         default={'product_uom_qty': math.ceil(remaining_yards / self.production_id.outs),
                    #                  'qty_done': math.ceil(remaining_yards / self.production_id.outs),
                    #                  'lot_id': new_rem_lot_rec and new_rem_lot_rec.id or False})
                    #     new_rem_lot_rec.customer_qty = remaining_yards
                    #     print ("\n\n\n 223333334444445555555555555", new_rem_lot_rec)
                    # mv_line.unlink()
                    # print ("mv_line", mv_line)
                        # while line_qty != 0:
                        #     if lot_required:
                        #         if not lot_rec:
                        #             lot_rec = self.env['stock.production.lot'].create({
                        #                 'product_id': mv_line.product_id.id,
                        #                 'company_id': mv_line.company_id.id,
                        #                 'name': f"{self.production_id.name}/{self.env['ir.sequence'].next_by_code('stock.lot.serial')}"
                        #             })
                        #     if line_qty < uom_put_up:
                        #         uom_put_up = line_qty
                        #     c_qty = 0
                        #     if customer_qty and uom_put_up and total_qty:
                        #         c_qty = (uom_put_up * customer_qty) / total_qty
                        #     new_mv_rec = mv_line.copy(
                        #         default={'product_uom_qty': uom_put_up,
                        #                  'qty_done': uom_put_up,
                        #                  'lot_id': lot_rec and lot_rec.id or False})
                        #
                        #     # lot_rec.customer_qty = round(c_qty)
                        #     # New Code for update
                        #     lot_rec.customer_qty = self.production_id.uom_put_up
                        #     lot_rec = False
                        #     line_qty -= uom_put_up

                        # pro_mv.move_line_ids = mv_data


                    # else:
                    #     if lot_rec and not lot_rec.customer_qty:
                    #         lot_rec.customer_qty = round(customer_qty)


class MrpProductProduceLine(models.TransientModel):
    _name = 'mrp.product.produce.line'
    _inherit = ["mrp.abstract.workorder.line"]
    _description = "Record production line"

    raw_product_produce_id = fields.Many2one('mrp.product.produce', 'Component in Produce wizard')
    finished_product_produce_id = fields.Many2one('mrp.product.produce', 'Finished Product in Produce wizard')

    @api.model
    def _get_raw_workorder_inverse_name(self):
        return 'raw_product_produce_id'

    @api.model
    def _get_finished_workoder_inverse_name(self):
        return 'finished_product_produce_id'

    def _get_final_lots(self):
        product_produce_id = self.raw_product_produce_id or self.finished_product_produce_id
        return product_produce_id.finished_lot_id | product_produce_id.finished_workorder_line_ids.mapped('lot_id')

    def _get_production(self):
        product_produce_id = self.raw_product_produce_id or self.finished_product_produce_id
        return product_produce_id.production_id

    @api.onchange('lot_id')
    def _onchange_lot_id(self):
        """ When the user is encoding a produce line for a tracked product, we apply some logic to
        help him. This onchange will automatically switch `qty_done` to 1.0.
        """
        if self.product_id.tracking == 'serial':
            if self.lot_id:
                self.qty_done = 1
            else:
                self.qty_done = 0