# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

_logger = logging.getLogger(__name__)

from odoo import api, fields, models
import math

class RollLines(models.TransientModel):
    _name = "roll.lines"
    _description = "Roll lines"
    _rec_name = "workorder_id"

    @api.model
    def default_get(self, default_fields):
        res = super(RollLines, self).default_get(default_fields)
        if self._context.get('active_id'):
            res['workorder_id'] = self._context.get('active_id')
            res['workcenter_id'] = self._context.get('workcenter_id')
        return res

    workorder_id = fields.Many2one('mrp.workorder', string='Work Order')
    workcenter_id = fields.Many2one('mrp.workcenter', 'Work Center')
    # roll_line_ids = fields.Many2many('mrp.wo.roll.line', string='Roll Lines')
    user_id = fields.Many2one("res.users", string='User', required=True)
    x_wiz_yards_in = fields.Integer('Yds in')
    x_wiz_yards_out = fields.Integer('Yds Out')
    roll_line_ids = fields.One2many('mrp.wo.roll.line.wiz', 'parent_roll_id', string='Roll Lines')
    final_roll_line_ids = fields.One2many('final.wo.roll.wiz', 'parent_roll_id',
                                          string='Final Roll Lines')

    def add_roll_lines_without_pause(self):
        vals = []
        if self.roll_line_ids:
            for rec in self.roll_line_ids:
                vals.append([0, 0, {
                    #'roll_id': rec.roll_id and rec.roll_id.id,
                    'roll_id': rec.existing_roll_id.id if rec.existing_roll_id else rec.roll_id and rec.roll_id.id,
                    'quantity': rec.quantity,
                    'consumed_qty': rec.consumed_qty,
                    'prev_roll_id': rec.prev_roll_id and rec.prev_roll_id.id,
                    'prev_roll_remained_qty': rec.prev_roll_remained_qty,
                    'full_consumed': rec.full_consumed,
                    'date_start': rec.date_start,
                    'user_id': rec.user_id and rec.user_id.id,
                    'workorder_id': self.workorder_id and self.workorder_id.id,
                }])
            if vals:
                self.workorder_id.roll_line_ids = [val for val in vals]
        elif self.final_roll_line_ids:
            for rec in self.final_roll_line_ids:
                vals.append((0, 0, {
                    'workorder_id': self.workorder_id and self.workorder_id.id,
                    'previous_roll_id': rec.previous_roll_id and rec.previous_roll_id.id,
                    'previous_roll_quantity' : rec.remained_qty,
                    'user_id': rec.user_id and rec.user_id.id,
                    'date_start': rec.date_start,
                    'is_fully_consumed': rec.is_fully_consumed,
                    'consumed_qty': rec.consumed_qty,
                    'total_qty': rec.total_qty,
                    'partial_done_qty': rec.partial_done_qty,
                }))
            if vals:
                self.workorder_id.final_roll_line_ids = vals

        # ── NEW: Preliminary roll cost split ─────────────────────────────────
        # Post preliminary per-roll values and Semi-Fin journal entries.
        # These will be corrected at button_finish with final labour values.
        if self.workorder_id:
            try:
                self.workorder_id._compute_roll_cost_split()
                if not self.workorder_id._is_last_workorder():
                    self.workorder_id._post_semifin_journal_entry()
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(
                    "Roll cost split failed on Add and Continue (non-blocking): %s", e
                )
        # ─────────────────────────────────────────────────────────────────────

        ctx = {
                'stop_user': self.user_id.id,
                'yds_in': self.x_wiz_yards_in,
                'yds_out': self.x_wiz_yards_out,
                'roll_id': self.workorder_id.roll_line_ids.ids[-1] if self.workorder_id.roll_line_ids else False,
                'quantity': self.workorder_id.roll_line_ids[-1].quantity if self.workorder_id.roll_line_ids else 0,
                "roll_rec": self.workorder_id.roll_line_ids,
            }
        return {
        'type': 'ir.actions.act_window_close'
        }   

    def add_roll_lines(self):
        vals = []
        if self.roll_line_ids:
            for rec in self.roll_line_ids:
                vals.append([0, 0, {
                    #'roll_id': rec.roll_id and rec.roll_id.id,
                    'roll_id': rec.existing_roll_id.id if rec.existing_roll_id else rec.roll_id and rec.roll_id.id,
                    'quantity': rec.quantity,
                    'consumed_qty': rec.consumed_qty,
                    'prev_roll_id': rec.prev_roll_id and rec.prev_roll_id.id,
                    'prev_roll_remained_qty': rec.prev_roll_remained_qty,
                    'full_consumed': rec.full_consumed,
                    'date_start': rec.date_start,
                    'user_id': rec.user_id and rec.user_id.id,
                    'workorder_id': self.workorder_id and self.workorder_id.id,
                }])
            if vals:
                self.workorder_id.roll_line_ids = [val for val in vals]
        elif self.final_roll_line_ids:
            for rec in self.final_roll_line_ids:
                vals.append((0, 0, {
                    'workorder_id': self.workorder_id and self.workorder_id.id,
                    'previous_roll_id': rec.previous_roll_id and rec.previous_roll_id.id,
                    'previous_roll_quantity' : rec.remained_qty,
                    'user_id': rec.user_id and rec.user_id.id,
                    'date_start': rec.date_start,
                    'is_fully_consumed': rec.is_fully_consumed,
                    'consumed_qty': rec.consumed_qty,
                    'total_qty': rec.total_qty,
                    'partial_done_qty': rec.partial_done_qty,
                }))
            if vals:
                self.workorder_id.final_roll_line_ids = vals

        # ── NEW: Preliminary roll cost split ─────────────────────────────────
        # Post preliminary per-roll values and Semi-Fin journal entries.
        # If from_done context → button_finish will recalculate with
        # final labour values immediately after this.
        if self.workorder_id:
            try:
                self.workorder_id._compute_roll_cost_split()
                if not self.workorder_id._is_last_workorder():
                    self.workorder_id._post_semifin_journal_entry()
            except Exception as e:
                import logging
                logging.getLogger(__name__).exception(
                    "Roll cost split failed on Add (non-blocking): %s", e
                )
        # ─────────────────────────────────────────────────────────────────────

        ctx = {
                'stop_user': self.user_id.id,
                'yds_in': self.x_wiz_yards_in,
                'yds_out': self.x_wiz_yards_out,
                'roll_id': self.workorder_id.roll_line_ids.ids[-1] if self.workorder_id.roll_line_ids else False,
                'quantity': self.workorder_id.roll_line_ids[-1].quantity if self.workorder_id.roll_line_ids else 0,
                "roll_rec": self.workorder_id.roll_line_ids,
            }
        if self._context.get('from_done'):
            self.workorder_id.with_context(ctx).button_finish()
        else:
            self.workorder_id.with_context(ctx).button_pending()
        # return {'type': 'ir.actions.act_window_close'}


class RollLinesWiz(models.TransientModel):
    _name = "mrp.wo.roll.line.wiz"
    _description = "Roll lines Wizard"
    _rec_name = "parent_roll_id"

    parent_roll_id = fields.Many2one('roll.lines', "Parent Roll", ondelete="cascade") #m2o
    prev_roll_ids = fields.Many2many(
        'mrp.production.roll',
        string='Previous Rolls',
        compute='_compute_prev_roll_ids',
        store=False
    )
    
    prev_roll_id = fields.Many2one('mrp.production.roll', 'Input Roll')
    roll_id = fields.Many2one('mrp.production.roll', 'Roll Id')
    quantity = fields.Float("Quantity")
    consumed_qty = fields.Float(string="Consumed Qty")
    prev_roll_remained_qty = fields.Float(
        string="Remaining Qty",
        readonly=True,
    )
    full_consumed = fields.Boolean(string="Fully Consumed")
    date_start = fields.Datetime('Start Date', default=fields.Datetime.now)
    user_id = fields.Many2one("res.users", string='User', required=True,
                                   related='parent_roll_id.user_id', copy=0)
    existing_roll_id = fields.Many2one(
        'mrp.production.roll',
        string='Existing Roll',
    )

    @api.depends('parent_roll_id.workorder_id')
    def _compute_prev_roll_ids(self):
        for rec in self:
            workorder = rec.parent_roll_id.workorder_id
            if not workorder and rec._context.get('workorder_id'):
                workorder = rec.env['mrp.workorder'].browse(rec._context.get('workorder_id'))
            if workorder:
                rec.prev_roll_ids = workorder.prev_roll_line_ids.mapped('roll_id')
            else:
                rec.prev_roll_ids = False

    def _get_workorder(self):
        """Helper to resolve workorder from parent or context."""
        workorder = self.parent_roll_id.workorder_id
        if not workorder and self._context.get('workorder_id'):
            workorder = self.env['mrp.workorder'].browse(
                self._context.get('workorder_id'))
        return workorder


    def _get_roll_base_and_consumed(self, workorder):
        base_qty = 0.0
        if workorder:
            prev_roll_line = workorder.prev_roll_line_ids.filtered(
                lambda l: l.roll_id.id == self.prev_roll_id.id
            )
            if prev_roll_line:
                base_qty = prev_roll_line[0].quantity
        if not base_qty:
            base_qty = self.prev_roll_id.total_qty or 0.0

        saved_consumed = sum(
            line.consumed_qty or 0.0
            for line in workorder.roll_line_ids
            if line.prev_roll_id
            and line.prev_roll_id.id == self.prev_roll_id.id
        ) if workorder else 0.0

        wizard_consumed = sum(
            line.consumed_qty or 0.0
            for line in self.parent_roll_id.roll_line_ids
            if line.prev_roll_id
            and line.prev_roll_id.id == self.prev_roll_id.id
            and line != self
        )

        _logger.info(
            "_get_roll_base_and_consumed: prev_roll=%s base_qty=%s "
            "saved_consumed=%s wizard_consumed=%s "
            "sibling_lines=%s",
            self.prev_roll_id.name,
            base_qty,
            saved_consumed,
            wizard_consumed,
            [(l.prev_roll_id.name if l.prev_roll_id else None,
              l.consumed_qty,
              l._origin.id,
              self._origin.id)
             for l in self.parent_roll_id.roll_line_ids],
        )

        return base_qty, saved_consumed, wizard_consumed

    # def _get_roll_base_and_consumed(self, workorder):
    #     base_qty = 0.0
    #     if workorder:
    #         prev_roll_line = workorder.prev_roll_line_ids.filtered(
    #             lambda l: l.roll_id == self.prev_roll_id
    #         )
    #         if prev_roll_line:
    #             base_qty = prev_roll_line[0].quantity
    #     if not base_qty:
    #         base_qty = self.prev_roll_id.total_qty or 0.0

    #     saved_consumed = sum(
    #         line.consumed_qty or 0.0
    #         for line in workorder.roll_line_ids
    #         if line.prev_roll_id == self.prev_roll_id
    #     ) if workorder else 0.0

    #     wizard_consumed = sum(
    #         line.consumed_qty or 0.0
    #         for line in self.parent_roll_id.roll_line_ids
    #         if line.prev_roll_id == self.prev_roll_id
    #         and line._origin.id != self._origin.id
    #     )

    #     return base_qty, saved_consumed, wizard_consumed

    # @api.onchange('add_to_existing_roll')
    # def _onchange_add_to_existing_roll(self):
    #     self.roll_id = False
    #     if self.add_to_existing_roll:
    #         workorder = self._get_workorder()
    #         self.existing_roll_workorder_id = workorder.id if workorder else 0
    #     else:
    #         self.existing_roll_workorder_id = 0

    @api.onchange('prev_roll_id')
    def _onchange_prev_roll_remained_qty(self):
        if not self.prev_roll_id or not self.parent_roll_id:
            self.prev_roll_remained_qty = 0.0
            self.consumed_qty = 0.0
            return

        workorder = self._get_workorder()
        base_qty, saved_consumed, wizard_consumed = \
            self._get_roll_base_and_consumed(workorder)
        remaining = max(base_qty - saved_consumed - wizard_consumed, 0.0)
        self.prev_roll_remained_qty = remaining

        if self.full_consumed:
            # Roll changed while full_consumed is checked — recalculate for new roll
            self.consumed_qty = remaining
            self.prev_roll_remained_qty = 0.0
        else:
            self.consumed_qty = 0.0

    @api.onchange('full_consumed')
    def _onchange_full_consumed(self):
        if not self.prev_roll_id or not self.parent_roll_id:
            return

        workorder = self._get_workorder()
        base_qty, saved_consumed, wizard_consumed = \
            self._get_roll_base_and_consumed(workorder)
        remaining = max(base_qty - saved_consumed - wizard_consumed, 0.0)

        if self.full_consumed:
            self.consumed_qty = remaining
            self.prev_roll_remained_qty = 0.0
        else:
            # Unchecked — clear consumed, restore remaining so user re-enters
            self.consumed_qty = 0.0
            self.prev_roll_remained_qty = remaining

    # @api.onchange('full_consumed')
    # def _onchange_full_consumed(self):
    #     workorder = self.parent_roll_id.workorder_id
    #     if not workorder and self._context.get('workorder_id'):
    #         workorder = self.env['mrp.workorder'].browse(self._context.get('workorder_id'))
    #     if self.full_consumed and self.prev_roll_id and workorder:
    #         consumed_so_far = sum(
    #             line.consumed_qty or 0.0
    #             for line in workorder.roll_line_ids
    #             if line.prev_roll_id == self.prev_roll_id
    #         )
    #         consumed_so_far += sum(
    #             line.consumed_qty or 0.0
    #             for line in self.parent_roll_id.roll_line_ids
    #             if line.prev_roll_id == self.prev_roll_id and line != self
    #         )
    #         self.consumed_qty = self.prev_roll_id.total_qty - consumed_so_far

    # @api.onchange('prev_roll_id')
    # def _onchange_prev_roll_remained_qty(self):
    #     if not self.prev_roll_id or not self.parent_roll_id:
    #         self.prev_roll_remained_qty = 0.0
    #         return

    #     workorder = self.parent_roll_id.workorder_id
    #     if not workorder and self._context.get('workorder_id'):
    #         workorder = self.env['mrp.workorder'].browse(
    #             self._context.get('workorder_id'))

    #     # Step 1: Get base quantity from prev_roll_line_ids (the authoritative source)
    #     # This is the quantity the previous WO produced for this roll
    #     base_qty = 0.0
    #     if workorder:
    #         prev_roll_line = workorder.prev_roll_line_ids.filtered(
    #             lambda l: l.roll_id == self.prev_roll_id
    #         )
    #         if prev_roll_line:
    #             base_qty = prev_roll_line[0].quantity

    #     # Fallback to roll's own total_qty if not found in prev_roll_line_ids
    #     if not base_qty:
    #         base_qty = self.prev_roll_id.total_qty or 0.0

    #     # Step 2: Already consumed in saved roll_line_ids on the workorder
    #     saved_consumed = 0.0
    #     if workorder:
    #         saved_consumed = sum(
    #             line.consumed_qty or 0.0
    #             for line in workorder.roll_line_ids
    #             if line.prev_roll_id == self.prev_roll_id
    #         )

    #     # Step 3: Consumed by OTHER lines in this wizard session (not self)
    #     # Use id comparison — safer than == on transient records
    #     wizard_consumed = sum(
    #         line.consumed_qty or 0.0
    #         for line in self.parent_roll_id.roll_line_ids
    #         if line.prev_roll_id == self.prev_roll_id
    #         and line._origin.id != self._origin.id  # exclude self safely
    #     )

    #     self.prev_roll_remained_qty = max(
    #         base_qty - saved_consumed - wizard_consumed, 0.0
    #     )

    # @api.onchange('prev_roll_id')
    # def _onchange_prev_roll_remained_qty(self):
    #     if not self.prev_roll_id or not self.parent_roll_id:
    #         self.prev_roll_remained_qty = 0.0
    #         return

    #     workorder = self.parent_roll_id.workorder_id
    #     if not workorder and self._context.get('workorder_id'):
    #         workorder = self.env['mrp.workorder'].browse(self._context.get('workorder_id'))

    #     prior_lines = []
    #     for line in self.parent_roll_id.roll_line_ids:
    #         if line == self:
    #             break  # stop at current line
    #         if line.prev_roll_id == self.prev_roll_id:
    #             prior_lines.append(line)

    #     wizard_consumed = sum(line.consumed_qty for line in prior_lines)

    #     remaining_qty = None
    #     computed_from_roll = False

    #     prev_roll_line = False
    #     if workorder:
    #         prev_roll_line = workorder.prev_roll_line_ids.filtered(lambda l: l.roll_id == self.prev_roll_id)
    #         if prev_roll_line:
    #             remaining_qty = prev_roll_line[0].quantity

    #     if remaining_qty is False or remaining_qty is None:
    #         remaining_qty = self.prev_roll_id.remained_qty
    #         computed_from_roll = True

    #     if remaining_qty is False or remaining_qty is None:
    #         computed_from_roll = False
    #         total_qty = self.prev_roll_id.total_qty
    #         if total_qty is not False and total_qty is not None:
    #             remaining_qty = total_qty
    #         elif prev_roll_line:
    #             remaining_qty = prev_roll_line[0].quantity
    #         if remaining_qty is False or remaining_qty is None:
    #             remaining_qty = 0.0

    #     if not computed_from_roll and workorder:
    #         existing_consumed = sum(
    #             line.consumed_qty or 0.0
    #             for line in workorder.roll_line_ids
    #             if line.prev_roll_id == self.prev_roll_id
    #         )
    #         remaining_qty -= existing_consumed

    #     self.prev_roll_remained_qty = max(remaining_qty - wizard_consumed, 0.0)




class FinalRollLinesWiz(models.TransientModel):
    _name = "final.wo.roll.wiz"
    _description = "Final Roll lines Wizard"
    _rec_name = "parent_roll_id"

    parent_roll_id = fields.Many2one('roll.lines', "Parent Roll", ondelete="cascade")
    workorder_id = fields.Many2one('mrp.workorder', related='parent_roll_id.workorder_id', string='Workorder')
    prev_roll_ids = fields.Many2many('mrp.wo.roll.line', string='Input Rolls', compute='_compute_prev_roll_ids', store=False)
    previous_roll_id = fields.Many2one('mrp.wo.roll.line', 'Input Roll')
    previous_roll_quantity = fields.Float(string="Quantity", readonly=True)
    date_start = fields.Datetime(string='Date', default=fields.Datetime.now)
    total_qty = fields.Float(string="Customer Qty")
    yards_qty = fields.Float(string="Qty(Yards)", compute="_compute_yards_qty")
    is_fully_consumed = fields.Boolean(string='Fully Consumed')
    consumed_qty = fields.Float(string="Consumed Qty")
    remained_qty = fields.Float(string="Remained Qty")
    partial_done_qty = fields.Float(string="Partially Done Quantity")
    user_id = fields.Many2one("res.users", string='User', required=True, related='parent_roll_id.user_id', copy=0)

    @api.depends('parent_roll_id.workorder_id')
    def _compute_prev_roll_ids(self):
        for rec in self:
            workorder = rec.parent_roll_id.workorder_id
            if workorder:
                rec.prev_roll_ids = workorder.prev_roll_line_ids
            else:
                rec.prev_roll_ids = False

    @api.depends('total_qty')
    def _compute_yards_qty(self):
        for rec in self:
            if rec.total_qty:
                if rec.workorder_id._origin.production_id and not rec.workorder_id._origin.production_id.origin:
                    rec.yards_qty = rec.total_qty
                else:
                    customer_qty = rec.total_qty or 0
                    customer_width = rec.workorder_id._origin and rec.workorder_id._origin.production_id and rec.workorder_id._origin.production_id.x_order_line_customer_mrp_width or 1
                    customer_length = rec.workorder_id._origin and rec.workorder_id._origin.production_id and rec.workorder_id._origin.production_id.x_order_line_customer_mrp_length or '0.0'
                    trim_width = rec.workorder_id._origin and rec.workorder_id._origin.production_id and rec.workorder_id._origin.production_id.x_order_line_trim_width
                    trim_length = rec.workorder_id._origin and rec.workorder_id._origin.production_id and rec.workorder_id._origin.production_id.x_order_line_trim_length
                    machine_length = rec.workorder_id._origin and rec.workorder_id._origin.production_id and rec.workorder_id._origin.production_id.x_order_line_machine_length or 41
                    component_width = rec.workorder_id._origin and rec.workorder_id._origin.production_id and rec.workorder_id._origin.production_id.move_raw_ids[0].product_id.x_item_width or 1
                    if customer_width == component_width:
                        trim_width = 0
                        Width_Outs = (int(component_width - trim_width) / customer_width) or 1
                        Width_Outs_split_Dec, Width_Outs_split_Frac = math.modf(Width_Outs)
                        Width_Outs_final = math.trunc(Width_Outs_split_Frac)
                        Master_Yards = int(customer_qty) / Width_Outs_final
                        if not Master_Yards.is_integer():
                            Master_Yards = int(Master_Yards) + 1
                        rec.yards_qty = Master_Yards
                    if customer_width != component_width and customer_length == '0.0':
                        Width_Outs = int((component_width - trim_width) / customer_width) or 1
                        Width_Outs_split_Dec, Width_Outs_split_Frac = math.modf(Width_Outs)
                        Width_Outs_final = math.trunc(Width_Outs_split_Frac)
                        Master_Yards = int(customer_qty) / Width_Outs_final
                        if not Master_Yards.is_integer():
                            Master_Yards = int(Master_Yards) + 1
                        rec.yards_qty = Master_Yards
                    if customer_length != '0.0':
                        Width_Outs = int((component_width - trim_width) / customer_width)
                        Width_Outs_split_Dec, Width_Outs_split_Frac = math.modf(Width_Outs)
                        Width_Outs_final = math.trunc(Width_Outs_split_Frac)
                        counter = 1
                        Length_Outs = (counter * customer_length) + trim_length
                        Length_Outs_split_Dec, Length_Outs_split_Frac = math.modf(Length_Outs)
                        Length_Outs_final = math.trunc(Length_Outs_split_Frac)
                        while Length_Outs_final < machine_length:
                            counter += 1
                            Length_Outs_final = (counter * customer_length) + trim_length
                        Length_Outs_final = counter - 1
                        Master_Sheet_Length = (Length_Outs_final * customer_length) + trim_length
                        machine_stops_ids = rec.env['machine.stops'].search([('x_machine_st', '>=', Master_Sheet_Length)], limit=1)
                        Master_Sheet_Length = machine_stops_ids.x_machine_st
                        Master_Outs = (Width_Outs_final * Length_Outs_final) or 1
                        Master_Sheets = (int(customer_qty) / Master_Outs)
                        if not Master_Sheets.is_integer():
                            Master_Sheets = int(Master_Sheets) + 1
                        Master_Yards = int(Master_Sheets * Master_Sheet_Length) / 36
                        if not Master_Yards.is_integer():
                            Master_Yards = int(Master_Yards) + 1
                        rec.yards_qty = Master_Yards
            else:
                rec.yards_qty = 0

    @api.onchange('is_fully_consumed')
    def _onchange_is_fully_consumed(self):
        workorder = self.parent_roll_id.workorder_id
        if not workorder and self._context.get('workorder_id'):
            workorder = self.env['mrp.workorder'].browse(
                self._context.get('workorder_id'))

        if not self.previous_roll_id or not workorder:
            return

        confirmed_consumed = sum(
            line.consumed_qty or 0.0
            for line in workorder.final_roll_line_ids
            if line.previous_roll_id.id == self.previous_roll_id.id
        )
        wizard_consumed = sum(
            line.consumed_qty or 0.0
            for line in self.parent_roll_id.final_roll_line_ids
            if line.previous_roll_id
            and line.previous_roll_id.id == self.previous_roll_id.id
            and line != self
        )
        remaining = max(
            self.previous_roll_id.quantity - confirmed_consumed - wizard_consumed,
            0.0
        )

        if self.is_fully_consumed:
            self.consumed_qty = remaining
            self.remained_qty = 0.0
        else:
            self.consumed_qty = 0.0
            self.remained_qty = remaining
            
    # @api.onchange('is_fully_consumed')
    # def _onchange_is_fully_consumed(self):
    #     workorder = self.parent_roll_id.workorder_id
    #     if not workorder and self._context.get('workorder_id'):
    #         workorder = self.env['mrp.workorder'].browse(
    #             self._context.get('workorder_id'))

    #     if not self.previous_roll_id or not workorder:
    #         return

    #     confirmed_consumed = sum(
    #         line.consumed_qty or 0.0
    #         for line in workorder.final_roll_line_ids
    #         if line.previous_roll_id == self.previous_roll_id
    #     )
    #     wizard_consumed = sum(
    #         line.consumed_qty or 0.0
    #         for line in self.parent_roll_id.final_roll_line_ids
    #         if line.previous_roll_id == self.previous_roll_id
    #         and line._origin.id != self._origin.id
    #     )
    #     remaining = self.previous_roll_id.quantity - confirmed_consumed - wizard_consumed

    #     if self.is_fully_consumed:
    #         self.consumed_qty = max(remaining, 0.0)
    #     else:
    #         self.consumed_qty = 0.0

    @api.onchange('previous_roll_id')
    def _compute_remained_qty(self):
        for rec in self:
            if not rec.previous_roll_id or not rec.parent_roll_id:
                rec.remained_qty = 0.0
                continue

            workorder = rec.parent_roll_id.workorder_id
            if not workorder:
                rec.remained_qty = 0.0
                continue

            confirmed_consumed = sum(
                line.consumed_qty for line in workorder.final_roll_line_ids
                if line.previous_roll_id.id == rec.previous_roll_id.id
            )

            wizard_consumed = sum(
                line.consumed_qty or 0.0
                for line in rec.parent_roll_id.final_roll_line_ids
                if line.previous_roll_id
                and line.previous_roll_id.id == rec.previous_roll_id.id
                and line != rec
            )

            rec.remained_qty = max(
                rec.previous_roll_id.quantity
                - confirmed_consumed
                - wizard_consumed,
                0.0
            )

    @api.onchange('consumed_qty')
    def _onchange_consumed_qty_update_siblings(self):
        if not self.previous_roll_id or not self.parent_roll_id:
            return

        workorder = self.parent_roll_id.workorder_id

        confirmed_consumed = sum(
            line.consumed_qty for line in workorder.final_roll_line_ids
            if line.previous_roll_id.id == self.previous_roll_id.id
        ) if workorder else 0.0

        for sibling in self.parent_roll_id.final_roll_line_ids:
            if not sibling.previous_roll_id:
                continue
            if sibling.previous_roll_id.id != self.previous_roll_id.id:
                continue
            if sibling == self:  # ← skip self
                continue
            wizard_consumed = sum(
                line.consumed_qty or 0.0
                for line in self.parent_roll_id.final_roll_line_ids
                if line.previous_roll_id
                and line.previous_roll_id.id == self.previous_roll_id.id
                and line != sibling
            )
            sibling.remained_qty = max(
                self.previous_roll_id.quantity
                - confirmed_consumed
                - wizard_consumed,
                0.0
            )

    # @api.onchange('previous_roll_id')
    # def _compute_remained_qty(self):
    #     for rec in self:
    #         if not rec.previous_roll_id or not rec.parent_roll_id:
    #             rec.remained_qty = 0.0
    #             continue

    #         workorder = rec.parent_roll_id.workorder_id
    #         if not workorder:
    #             rec.remained_qty = 0.0
    #             continue

    #         confirmed_consumed = sum(
    #             line.consumed_qty for line in workorder.final_roll_line_ids
    #             if line.previous_roll_id == rec.previous_roll_id
    #         )
    #         wizard_consumed = sum(
    #             line.consumed_qty for line in rec.parent_roll_id.final_roll_line_ids
    #             if line.previous_roll_id == rec.previous_roll_id
    #             and line._origin.id != rec._origin.id
    #         )
    #         rec.remained_qty = rec.previous_roll_id.quantity - confirmed_consumed - wizard_consumed

    # @api.onchange('is_fully_consumed')
    # def _onchange_is_fully_consumed(self):
    #     workorder = self.parent_roll_id.workorder_id
    #     if not workorder and self._context.get('workorder_id'):
    #         workorder = self.env['mrp.workorder'].browse(self._context.get('workorder_id'))

    #     if self.is_fully_consumed and self.previous_roll_id and workorder:
    #         consumed_so_far = sum(
    #             line.consumed_qty or 0.0
    #             for line in workorder.roll_line_ids
    #             if line.prev_roll_id == self.previous_roll_id
    #         )

    #         wizard_consumed = sum(
    #             line.consumed_qty or 0.0
    #             for line in self.parent_roll_id.final_roll_line_ids
    #             if line.previous_roll_id == self.previous_roll_id and line != self
    #         )

    #         total_consumed = consumed_so_far + wizard_consumed

    #         self.consumed_qty = self.previous_roll_id.quantity - total_consumed

    # @api.onchange('previous_roll_id')
    # def _compute_remained_qty(self):
    #     for rec in self:
    #         if not rec.previous_roll_id or not rec.parent_roll_id:
    #             rec.remained_qty = 0.0
    #             continue

    #         workorder = rec.parent_roll_id.workorder_id
    #         if not workorder:
    #             rec.remained_qty = 0.0
    #             continue

    #         # Step 1: Already consumed in confirmed final.wo.roll
    #         confirmed_consumed = sum(
    #             line.consumed_qty for line in workorder.final_roll_line_ids
    #             if line.previous_roll_id == rec.previous_roll_id
    #         )

    #         # Step 2: Additional draft lines in current wizard, excluding self
    #         wizard_consumed = sum(
    #             line.consumed_qty for line in rec.parent_roll_id.final_roll_line_ids
    #             if line.previous_roll_id == rec.previous_roll_id and line != rec
    #         )

    #         total_consumed = confirmed_consumed + wizard_consumed

    #         # Step 3: Final remaining qty
    #         rec.remained_qty = rec.previous_roll_id.quantity - total_consumed


    # @api.depends('total_qty', 'consumed_qty')
    # def _compute_remained_qty(self):
    #     for rec in self:
    #         rec.remained_qty = rec.previous_roll_quantity - rec.consumed_qty