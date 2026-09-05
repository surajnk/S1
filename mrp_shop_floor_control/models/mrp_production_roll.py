# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime

import logging

_logger = logging.getLogger(__name__)

class MrpProductionRoll(models.Model):
    _name = 'mrp.production.roll'

    name = fields.Char('Roll Id', required=1, default="New")

    lot_id = fields.Many2one(
        'stock.production.lot',
        string='Lot/Serial Number',
        readonly=True,
        copy=False,
    )

    consumed_qty = fields.Float("Total Consumed", compute="_compute_consumed_qty", store=True)
    remained_qty = fields.Float("Remaining Qty", compute="_compute_consumed_qty", store=True)
    total_qty = fields.Float("Initial Roll Qty", default=0.0)
    roll_line_ids = fields.One2many('mrp.wo.roll.line', 'prev_roll_id', string='Consumed In Lines')

    # ── NEW: Roll WIP value ───────────────────────────────────────────────────
    # Updated at each workorder completion by _compute_roll_cost_split()
    # on mrp.workorder. Shows the current fully loaded cost of this roll
    # at its latest completed workorder stage.
    #
    # Example:
    #   After Coating  → roll_wip_value = $1,875
    #   After Embossing → roll_wip_value = $2,500
    #   After Sheeting  → roll_wip_value = $3,125
    roll_wip_value = fields.Float(
        string='Roll WIP Value',
        digits='Product Price',
        readonly=True,
        copy=False,
        help="Current fully loaded cost of this roll at its latest "
             "completed workorder stage. Updated automatically at each "
             "workorder completion.",
    )

    original_wip_value = fields.Float(
        string='Original WIP Value',
        digits='Product Price',
        readonly=True,
        copy=False,
        help="Full cost of this roll when first calculated at its workorder. "
             "Never changes — used as basis for remaining value calculation.",
    )

    roll_material_value = fields.Float(
        string='Material Value',
        digits='Product Price',
        readonly=True,
        copy=False,
    )

    material_cost_rate = fields.Float(
        string='Material Cost Rate',
        digits='Product Price',
        compute='_compute_material_cost_rate',
        store=False,
        help="Material cost per yard = material value / initial qty.",
    )

    @api.depends('roll_material_value', 'total_qty')
    def _compute_material_cost_rate(self):
        for roll in self:
            if roll.total_qty:
                roll.material_cost_rate = round(
                    roll.roll_material_value / roll.total_qty, 4)
            else:
                roll.material_cost_rate = 0.0

    @api.depends('roll_line_ids.consumed_qty')
    def _compute_consumed_qty(self):
        for roll in self:
            roll.consumed_qty = sum(roll.roll_line_ids.mapped('consumed_qty'))
            roll.remained_qty = roll.total_qty - roll.consumed_qty
            _logger.info("ROLL: %s | Total: %s | Consumed: %s | Remaining: %s",
                        roll.name, roll.total_qty, roll.consumed_qty, roll.remained_qty)

    # @api.depends()
    # def _compute_consumed_qty(self):
    #     for roll in self:
    #         lines = self.env['mrp.wo.roll.line'].search([('prev_roll_id', '=', roll.id)])
    #         roll.consumed_qty = sum(lines.mapped('consumed_qty'))
    #         roll.remained_qty = roll.total_qty - roll.consumed_qty
    #         _logger.info("ROLL: %s | Total: %s | Consumed: %s | Remaining: %s",
    #                  roll.name, roll.total_qty, roll.consumed_qty, roll.remained_qty)

    # @api.model
    # def default_get(self, fields):
    #     rec = super(MrpProductionRoll, self).default_get(fields)
    #     if self._context.get('get_default_roll'):
    #         rec['name'] = self.env['ir.sequence'].next_by_code('mrp.production.roll')
    #     return rec

    @api.model
    def create(self, vals):
        if vals.get('name') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('mrp.production.roll')
        res = super(MrpProductionRoll, self).create(vals)
        return res


    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if self._context.get('workorder_id') and not self._context.get('get_existing_roll_from_workorder_id'):
            wo_rec = self.env['mrp.workorder'].browse(self._context.get('workorder_id'))
            roll_ids = wo_rec.prev_roll_line_ids.mapped("roll_id")
            if roll_ids:
                args += [('id', 'in', roll_ids.ids)]
        return super(MrpProductionRoll, self)._name_search(name=name, args=args, operator=operator, limit=limit,
                                                 name_get_uid=name_get_uid)

class MrpWoRollLine(models.Model):
    _name = 'mrp.wo.roll.line'
    _rec_name = 'roll_id'

    prev_roll_ids = fields.Many2many(
        'mrp.production.roll', string='Previous Rolls', compute='_compute_prev_roll_ids', store=False
    )

    # roll_material_value = fields.Float(
    #     string='Roll Material Value',
    #     digits='Product Price',
    #     readonly=True,
    #     copy=False,
    #     help="Material cost allocated to this roll.\n"
    #          "First WO: AVCO of input roll × consumed quantity.\n"
    #          "Subsequent WOs: carried forward from previous roll value.",
    # )

    # # ── Component 2: Labour + Overhead cost ───────────────────────────────────
    # # WO total labour + overhead × (this roll yards / total yards at WO)
    # roll_labour_ovh_value = fields.Float(
    #     string='Roll Labour & Overhead Value',
    #     digits='Product Price',
    #     readonly=True,
    #     copy=False,
    #     help="Labour and overhead cost allocated to this roll "
    #          "proportional to yards: "
    #          "(this roll yards / total yards at WO) × WO lab+ovh cost.",
    # )

    # # ── Total roll value ──────────────────────────────────────────────────────
    # # roll_material_value + roll_labour_ovh_value
    # # Also written to mrp.production.roll.roll_wip_value for visibility
    # roll_wip_value = fields.Float(
    #     string='Roll WIP Value',
    #     digits='Product Price',
    #     readonly=True,
    #     copy=False,
    #     help="Total cost allocated to this roll = "
    #          "material value + labour & overhead value.",
    # )

    # # ── Journal entry reference ───────────────────────────────────────────────
    # # One Semi-Fin journal entry per roll per workorder
    # # CR WIP / DR Semi-Fin posted when roll is added at workorder
    # # Reversed when next workorder starts
    # roll_journal_entry_id = fields.Many2one(
    #     'account.move',
    #     string='Semi-Fin Journal Entry',
    #     copy=False,
    #     readonly=True,
    #     help="Semi-Fin journal entry posted for this roll at workorder "
    #          "completion. Reversed when next workorder starts.",
    # )

    # # workcenter_id = fields.Many2one(
    # #     'mrp.workcenter',
    # #     string='Work Center',
    # #     related='workorder_id.workcenter_id',
    # #     store=False,
    # # )

    # production_id = fields.Many2one(
    #     'mrp.production',
    #     string='Manufacturing Order',
    #     related='workorder_id.production_id',
    #     store=False,
    # )
 

    @api.depends('workorder_id')
    def _compute_prev_roll_ids(self):
        for rec in self:
            if rec.workorder_id:
                # Fetch the roll IDs from the related work order
                rec.prev_roll_ids = rec.workorder_id.prev_roll_line_ids.mapped('roll_id')
            else:
                rec.prev_roll_ids = False

    @api.depends('workorder_id')
    def _compute_prev_work_order(self):
        for rec in self:
            workorder = rec.workorder_id
            if workorder:
                workorder.re_arrange_pre_next_work_order()
                # prev_work_order = workorder.next_work_order_id
                rec.prev_work_order_id = workorder.next_work_order_id
                # rec.prev_work_order_id = prev_work_order
        return True

    roll_id = fields.Many2one('mrp.production.roll', 'Roll Id')
    prev_roll_id = fields.Many2one('mrp.production.roll', 'Input Roll')
    quantity = fields.Float("Quantity")
    workorder_id = fields.Many2one('mrp.workorder', "Workorder")
    prev_work_order_id = fields.Many2one(
        'mrp.workorder', 'Previous Work Order', compute="_compute_prev_work_order", store="True")
    date = date_start = fields.Datetime('Start Date', required=True, tracking=True, default=fields.Datetime.now)
    consumed_qty = fields.Float(string="Consumed Qty", copy=False)
    prev_roll_remained_qty = fields.Float(
        string="Remaining Qty",
        store=True,
        readonly=True
    )
    full_consumed = fields.Boolean(
        string="Fully Consumed",
    )


    @api.onchange('full_consumed')
    def _onchange_full_consumed(self):
        if self.full_consumed and self.prev_roll_id:
            consumed_so_far = sum(
                line.consumed_qty or 0.0
                for line in self.workorder_id.roll_line_ids
                if line.id != self.id and line.prev_roll_id == self.prev_roll_id
            )
            self.consumed_qty = self.prev_roll_id.total_qty - consumed_so_far


    def _line_consumption(self, line):
        """Return the quantity to subtract for a related roll line."""
        return line.consumed_qty or line.quantity or 0.0

    def _compute_prev_roll_remaining_qty(self, workorder=None, prev_roll=None, exclude_line=None):
        workorder = workorder or self.workorder_id
        prev_roll = prev_roll or self.prev_roll_id

        if not workorder or not prev_roll:
            return 0.0

        prev_roll_lines = workorder.prev_roll_line_ids.filtered(lambda line: line.roll_id == prev_roll)
        if prev_roll_lines:
            base_available = sum(prev_roll_lines.mapped('quantity'))
        else:
            base_available = prev_roll.remained_qty or prev_roll.total_qty or 0.0

        related_lines = workorder.roll_line_ids.filtered(
            lambda line: line.prev_roll_id == prev_roll and line != (exclude_line or self)
        )
        consumed_so_far = sum(self._line_consumption(line) for line in related_lines)

        return max(base_available - consumed_so_far, 0.0)

    def _sync_prev_roll_remained_qty(self):
        for rec in self:
            if not rec.prev_roll_id or not rec.workorder_id:
                continue

            remaining_qty = rec._compute_prev_roll_remaining_qty(
                workorder=rec.workorder_id,
                prev_roll=rec.prev_roll_id,
                exclude_line=rec,
            )

            rec.with_context(skip_remained_update=True).write({
                'prev_roll_remained_qty': remaining_qty,
            })

    @api.onchange('prev_roll_id', 'workorder_id', 'consumed_qty')
    def _onchange_prev_roll_remained_qty(self):
        if not self.prev_roll_id or not self.workorder_id:
            self.prev_roll_remained_qty = 0.0
            return

        self.prev_roll_remained_qty = self._compute_prev_roll_remaining_qty()

    @api.model
    def create(self, vals):
        rec = super().create(vals)

        # When a new roll is created from the roll line, ensure that its
        # total quantity matches the quantity entered on the line.  This
        # value is later used by the next work order to compute the
        # remaining quantity of the roll.
        if rec.roll_id and not rec.roll_id.total_qty:
            rec.roll_id.total_qty = rec.quantity

        rec._sync_prev_roll_remained_qty()

        if rec.prev_roll_id and rec.consumed_qty:
            source_roll = rec.prev_roll_id
            total_qty = source_roll.total_qty or 0.0
            original_value = source_roll.original_wip_value or 0.0

            if total_qty and original_value:
                total_consumed = sum(
                    source_roll.roll_line_ids.mapped('consumed_qty')
                )
                remaining_qty = max(total_qty - total_consumed, 0.0)

                if remaining_qty <= 0:
                    new_value = 0.0
                else:
                    new_value = round(
                        original_value * (remaining_qty / total_qty), 2
                    )

                source_roll.with_context(
                    skip_remained_update=True
                ).write({'roll_wip_value': new_value})

                _logger.info(
                    "CREATE Roll %s: consumed=%s remaining=%s "
                    "original=%s new_value=%s",
                    source_roll.name, total_consumed,
                    remaining_qty, original_value, new_value,
                )
        # ─────────────────────────────────────────────────────────────────


        return rec

    def write(self, vals):
        skip_flag = self.env.context.get('skip_remained_update')
        res = super().write(vals)

        if not skip_flag:
            self._sync_prev_roll_remained_qty()

            # ── Update source roll WIP value on consumption ───────────────
            if 'consumed_qty' in vals:
                for rec in self:
                    if not rec.prev_roll_id:
                        continue
                    source_roll = rec.prev_roll_id
                    total_qty = source_roll.total_qty or 0.0
                    original_value = source_roll.original_wip_value or 0.0

                    if total_qty and original_value:
                        total_consumed = sum(
                            source_roll.roll_line_ids.mapped('consumed_qty')
                        )
                        remaining_qty = max(total_qty - total_consumed, 0.0)

                        if remaining_qty <= 0:
                            new_value = 0.0
                        else:
                            new_value = round(
                                original_value * (remaining_qty / total_qty), 2
                            )

                        source_roll.with_context(
                            skip_remained_update=True
                        ).write({'roll_wip_value': new_value})

                        _logger.info(
                            "Roll %s: consumed=%s remaining=%s "
                            "original=%s new_value=%s",
                            source_roll.name, total_consumed,
                            remaining_qty, original_value, new_value,
                        )
            # ─────────────────────────────────────────────────────────────

        return res
    # def write(self, vals):
    #     skip_flag = self.env.context.get('skip_remained_update')
    #     res = super().write(vals)

    #     if not skip_flag:
    #         self._sync_prev_roll_remained_qty()

    #     return res

    # def write(self, vals):
    #     res = super().write(vals)

    #     for rec in self:
    #         if rec.prev_roll_id and rec.workorder_id:
    #             consumed_so_far = sum(
    #                 line.consumed_qty or 0.0
    #                 for line in rec.workorder_id.roll_line_ids
    #                 if line.id != rec.id and line.prev_roll_id == rec.prev_roll_id
    #             )
    #             rec.prev_roll_remained_qty = rec.prev_roll_id.total_qty - consumed_so_far

    #     return res



    @api.onchange('workorder_id')
    def _onchange_workorder_id(self):
        if self.workorder_id:
            roll_ids = self.workorder_id.prev_roll_line_ids.mapped('roll_id').ids
            return {
                'domain': {
                    'prev_roll_id': [('id', 'in', roll_ids)]
                }
            }