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
            # Improve code in future
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
    # @api.model
    # def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
    #     _logger.info("2222222222222222",self._context.get('get_prev_roll_from_workorder_id'))
    #     _logger.info(
    #         "MrpProductionRoll._name_search FULL context=%s",
    #         self._context
    #     )
    #     if self._context.get('get_prev_roll_from_workorder_id'):
    #         workorder_id = self.env['mrp.workorder'].sudo().browse(int(self._context.get('get_prev_roll_from_workorder_id')))
    #         roll_ids = []
    #         if workorder_id:
    #             roll_ids = workorder_id.prev_roll_line_ids.ids
    #         args = [('id', 'in', roll_ids)]
    #     print ("\n\n\n s11111111111111111111elf", self._context)
    #     return super(MrpProductionRoll, self)._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)


class MrpWoRollLine(models.Model):
    _inherit = 'mrp.wo.roll.line'

    user_id = fields.Many2one('res.users', string='Users', copy=0, required=1)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center',
                                    related='workorder_id.workcenter_id', copy=0)
    status = fields.Selection([('available', 'Available'),('done', 'Done')], string='Status',
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
    
    # @api.model
    # def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
    #     if self._context.get('get_prev_roll_from_workorder_id'):
    #         workorder_id = self.env['mrp.workorder'].sudo().browse(int(self._context.get('get_prev_roll_from_workorder_id')))
    #         roll_ids = []
    #         if workorder_id:
    #             roll_ids = workorder_id.prev_roll_line_ids.filtered(lambda x: x.status == 'available').ids
    #         args = [('id', 'in', roll_ids)]
    #     return super(MrpWoRollLine, self)._name_search(name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)
    

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
                    workorder.with_context(skip_roll_transfer_move=True)._create_pick_and_moves_for_output_rolls(lines=wo_lines)
                except Exception as err:
                    _logger.exception("Failed to auto-transfer roll output for WO %s: %s", workorder.id, err)

        return records

    def write(self, vals):
        res = super(MrpWoRollLine, self).write(vals)
        for line in self:
            if line.prev_roll_id:
                total = self.search([('prev_roll_id', '=', line.prev_roll_id.id)]).mapped('consumed_qty')
                line.prev_roll_id.consumed_qty = sum(total)
        return res
