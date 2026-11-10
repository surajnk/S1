# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class FinalWoRollInput(models.Model):
    """One input roll consumed by a Final Yield line (``final.wo.roll``).

    A Final Yield line still produces ONE output roll (``total_qty`` /
    ``yards_qty`` stay on the parent). This model lets that single output be
    fed by several input rolls, each with its own consumed quantity and its
    own "fully consumed" flag.

    The parent keeps the legacy single-roll fields (``previous_roll_id``,
    ``previous_roll_quantity``, ``consumed_qty``, ``is_fully_consumed``) and
    mirrors the children into them (see
    ``final.wo.roll._refresh_from_input_lines``). A parent line without
    children is a legacy line and keeps whatever is stored on it.
    """
    _name = 'final.wo.roll.input'
    _description = 'Final Roll Input Roll'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    final_roll_id = fields.Many2one(
        'final.wo.roll', string='Final Roll Line', required=True,
        ondelete='cascade', index=True)
    workorder_id = fields.Many2one(
        'mrp.workorder', related='final_roll_id.workorder_id',
        string='Workorder', store=True, index=True, readonly=True)
    previous_roll_id = fields.Many2one(
        'mrp.wo.roll.line', string='Input Roll', required=True, copy=False)
    previous_roll_quantity = fields.Float(string='Quantity')
    consumed_qty = fields.Float(string='Consumed Qty', copy=False)
    is_fully_consumed = fields.Boolean(string='Fully Consumed', copy=False)
    remained_qty = fields.Float(
        string='Remained Qty', compute='_compute_remained_qty', store=True)

    _sql_constraints = [
        ('final_roll_input_roll_uniq',
         'unique(final_roll_id, previous_roll_id)',
         'The same input roll cannot be added twice to one Final Roll line.'),
    ]

    @api.depends('previous_roll_quantity', 'consumed_qty')
    def _compute_remained_qty(self):
        for rec in self:
            rec.remained_qty = rec.previous_roll_quantity - rec.consumed_qty

    @api.onchange('previous_roll_id')
    def _onchange_previous_roll_id_quantity(self):
        if self.previous_roll_id:
            self.previous_roll_quantity = self.previous_roll_id.quantity

    # ── roll status ───────────────────────────────────────────────────────
    # The Input Roll picker only lists rolls whose status is 'available'
    # (see mrp.wo.roll.line._name_search), so a roll that is fully consumed
    # must be moved to 'done', and moved back when nothing marks it fully
    # consumed any more. Done here (not in an onchange) so it holds however
    # the line is saved: wizard, workorder form or code.

    @api.model
    def _roll_is_fully_consumed(self, roll):
        if self.search_count([
                ('previous_roll_id', '=', roll.id),
                ('is_fully_consumed', '=', True)]):
            return True
        # Legacy final lines (no input lines) carry the roll on the parent.
        return bool(self.env['final.wo.roll'].search_count([
            ('previous_roll_id', '=', roll.id),
            ('is_fully_consumed', '=', True),
            ('input_line_ids', '=', False)]))

    @api.model
    def _set_roll_status(self, rolls):
        for roll in rolls.exists():
            status = 'done' if self._roll_is_fully_consumed(roll) else 'available'
            if roll.status != status:
                roll.status = status

    def _after_input_change(self, old_rolls=None):
        for rec in self:
            # Same bookkeeping the legacy parent did on its single roll.
            rec.previous_roll_id.remained_qty = rec.remained_qty
        self._set_roll_status(self.mapped('previous_roll_id') | (old_rolls or self.env['mrp.wo.roll.line']))
        self.mapped('final_roll_id')._refresh_from_input_lines()

    # ── CRUD ──────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._after_input_change()
        return recs

    def write(self, vals):
        old_rolls = self.mapped('previous_roll_id') if 'previous_roll_id' in vals else None
        res = super().write(vals)
        if {'previous_roll_id', 'previous_roll_quantity', 'consumed_qty',
                'is_fully_consumed'} & set(vals):
            self._after_input_change(old_rolls)
        return res

    def unlink(self):
        rolls = self.mapped('previous_roll_id')
        parents = self.mapped('final_roll_id')
        res = super().unlink()
        self._set_roll_status(rolls)
        # When the parent itself is being deleted it must not be refreshed.
        if not self.env.context.get('final_roll_parent_unlink'):
            parents.exists()._refresh_from_input_lines()
        return res
