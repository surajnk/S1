# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)

from odoo import models, fields, api, _


class MrpProductionRoll(models.Model):
    _inherit = 'mrp.production.roll'

    @api.model
    def create(self, vals):
        if vals.get('name') == 'New':
            production_name = False
            if self._context.get('workorder_id'):
                workorder_id = self.env['mrp.workorder'].browse(int(self._context.get('workorder_id')))
                production_name = workorder_id.production_id.name
                if production_name:
                    production_name = production_name.split('/', 1) and production_name.split('/', 1)[1]
            roll_id = self.search([('name', 'ilike', production_name)])
            next_roll = 0
            if roll_id:
                next_roll = "%04d" % (int(roll_id[-1].name.split('/')[-1]) + 1)
            else:
                next_roll = "%04d" % (1)
            if production_name:
                vals['name'] = f"{production_name}/{next_roll}"
            else:
                vals['name'] = next_roll
        res = super(MrpProductionRoll, self).create(vals)
        return res

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if self._context.get('get_prev_roll_from_workorder_id'):
            workorder_id = self.env['mrp.workorder'].sudo().browse(
                int(self._context.get('get_prev_roll_from_workorder_id')))
            roll_ids = []
            if workorder_id:
                roll_ids = workorder_id.prev_roll_line_ids.ids
            args = [('id', 'in', roll_ids)]
        elif self._context.get('get_existing_roll_from_workorder_id'):
            workorder_id = self.env['mrp.workorder'].sudo().browse(
                int(self._context.get('get_existing_roll_from_workorder_id')))
            roll_ids = workorder_id.roll_line_ids.mapped(
                'roll_id').filtered(bool).ids if workorder_id else []
            args = [('id', 'in', roll_ids)]
        return super(MrpProductionRoll, self)._name_search(
            name=name, args=args, operator=operator,
            limit=limit, name_get_uid=name_get_uid)


class MrpWoRollLine(models.Model):
    _inherit = 'mrp.wo.roll.line'

    user_id = fields.Many2one('res.users', string='Users', copy=0, required=1)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center',
                                    related='workorder_id.workcenter_id', copy=0)
    status = fields.Selection([('available', 'Available'), ('done', 'Done')], string='Status',
                               tracking=True, copy=False, default='available')
    remained_qty = fields.Float(string="Remained Qty", copy=0, readonly=0)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if self._context.get('get_prev_roll_from_workorder_id'):
            workorder_id = self.env['mrp.workorder'].sudo().browse(
                int(self._context.get('get_prev_roll_from_workorder_id')))
            roll_ids = []
            if workorder_id:
                seen_rolls = set()
                for line in workorder_id.prev_roll_line_ids.filtered(
                        lambda x: x.status == 'available' and x.quantity > 0):
                    if line.roll_id.id not in seen_rolls:
                        seen_rolls.add(line.roll_id.id)
                        roll_ids.append(line.id)
            args = [('id', 'in', roll_ids)]
        return super(MrpWoRollLine, self)._name_search(
            name=name, args=args, operator=operator,
            limit=limit, name_get_uid=name_get_uid)

    def _create_wc_receipt_move(self, line):
        workorder = line.workorder_id
        _logger.info("_create_wc_receipt_move START: line=%s workorder=%s", line.id, workorder)
        
        if not workorder:
            _logger.warning("No workorder on line %s", line.id)
            return False

        src_loc = self.env.ref('stock.location_inventory', raise_if_not_found=False) or self.env['stock.location'].search([('usage', '=', 'inventory'),('company_id', 'in', [workorder.company_id.id, False]),], limit=1)
        dest_loc = workorder.workcenter_id.location_id if workorder.workcenter_id else False

        _logger.info("src_loc=%s dest_loc=%s", src_loc, dest_loc)

        if not src_loc or not dest_loc:
            _logger.warning("Missing locations: src=%s dest=%s", src_loc, dest_loc)
            return False

        production = workorder.production_id
        product = production.product_id
        uom = production.product_uom_id
        qty = line.remained_qty or line.quantity or 0.0

        _logger.info("product=%s uom=%s qty=%s roll_id=%s", product, uom, qty, line.roll_id)

        if not qty:
            _logger.warning("Zero qty for line %s", line.id)
            return False

        lot = False
        if line.roll_id:
            lot_name = line.roll_id.name
            _logger.info("Looking for lot: name=%s product=%s company=%s", 
                         lot_name, product.id, workorder.company_id.id)
            existing_lot = self.env['stock.production.lot'].search([
                ('name', '=', lot_name),
                ('product_id', '=', product.id),
                ('company_id', '=', workorder.company_id.id),
            ], limit=1)
            if existing_lot:
                lot = existing_lot.id
                _logger.info("Found existing lot: %s", lot)
            else:
                lot = self.env['stock.production.lot'].create({
                    'name': lot_name,
                    'product_id': product.id,
                    'company_id': workorder.company_id.id,
                }).id
                _logger.info("Created new lot: %s", lot)

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', workorder.company_id.id),
        ], limit=1)
        _logger.info("picking_type=%s", picking_type)
        
        if not picking_type:
            _logger.warning("No internal picking type found")
            return False

        origin = production.name or _('MO/%s') % production.id
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src_loc.id,
            'location_dest_id': dest_loc.id,
            'origin': origin,
            'company_id': workorder.company_id.id,
            'move_type': 'direct',
        })
        _logger.info("Created picking: %s", picking.name)

        mv = self.env['stock.move'].create({
            'name': '%s: %s' % (workorder.workcenter_id.name or '', product.display_name),
            'product_id': product.id,
            'product_uom': uom.id,
            'product_uom_qty': qty,
            'location_id': src_loc.id,
            'location_dest_id': dest_loc.id,
            'picking_id': picking.id,
            'origin': origin,
            'company_id': workorder.company_id.id,
        })
        _logger.info("Created move: %s state=%s", mv.id, mv.state)

        picking.with_context(immediate_transfer=True).action_confirm()
        _logger.info("After confirm: picking state=%s move state=%s move_lines=%s", 
                     picking.state, mv.state, mv.move_line_ids.ids)

        if mv.move_line_ids:
            mv.move_line_ids.write({'lot_id': lot or False, 'qty_done': qty})
            _logger.info("Updated existing move lines: %s", mv.move_line_ids.ids)
        else:
            ml = self.env['stock.move.line'].create({
                'move_id': mv.id,
                'picking_id': picking.id,
                'product_id': product.id,
                'product_uom_qty': qty,
                'qty_done': qty,
                'product_uom_id': uom.id,
                'location_id': src_loc.id,
                'location_dest_id': dest_loc.id,
                'lot_id': lot or False,
            })
            _logger.info("Created new move line: %s", ml.id)

        try:
            picking.with_context(
                skip_immediate=True,
                skip_backorder=True,
                picking_ids_not_to_backorder=picking.ids,
                skip_roll_transfer_move=True,
            ).button_validate()
            _logger.info("Auto-validated picking %s state=%s", picking.name, picking.state)
        except Exception as e:
            _logger.exception("Failed to auto-validate picking %s: %s", picking.name, e)

        return picking

    @api.model_create_multi
    def create(self, vals_list):
        records = super(MrpWoRollLine, self).create(vals_list)

        for line in records:
            if line.prev_roll_id:
                line.prev_roll_id.consumed_qty += line.consumed_qty

        if not self.env.context.get('skip_roll_transfer_move'):
            for workorder in records.mapped('workorder_id'):
                wo_lines = records.filtered(lambda l: l.workorder_id == workorder)
                try:
                    # Step 1 — seed stock into WC location from Virtual/Production
                    for line in wo_lines:
                        self._create_wc_receipt_move(line)

                    # Step 2 — create outbound transfer WC → next WC (left for operator)
                    workorder.with_context(
                        skip_roll_transfer_move=True
                    )._create_pick_and_moves_for_output_rolls(lines=wo_lines)

                except Exception as err:
                    _logger.exception(
                        "Failed to auto-transfer roll output for WO %s: %s",
                        workorder.id, err
                    )

        return records

    def write(self, vals):
        res = super(MrpWoRollLine, self).write(vals)
        for line in self:
            if line.prev_roll_id:
                total = self.search([('prev_roll_id', '=', line.prev_roll_id.id)]).mapped('consumed_qty')
                line.prev_roll_id.consumed_qty = sum(total)
        return res