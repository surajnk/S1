# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging
from collections import defaultdict
from pytz import timezone, utc
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    # ── Existing fields ────────────────────────────────────────────────────────
    qty_production = fields.Float('Manufacturing Order Qty')
    duration = fields.Float('Elapsed')
    duration_hours = fields.Float(
        string='Elapsed Hrs', compute='_compute_duration_hours', store=True)
    name = fields.Char(string='Name')
    date_actual_start_wo = fields.Datetime(
        'Actual Start Date', compute='_compute_dates_actual', store=True)
    date_actual_finished_wo = fields.Datetime(
        'Actual End Date', compute='_compute_dates_actual', store=True)
    date_planned_start_wo = fields.Datetime(
        'Sched Start Date', readonly=True,
        copy=False)
    date_planned_finished_wo = fields.Datetime(
        'Sched End Date', readonly=True,
        copy=False)
    qty_output_wo = fields.Float(
        'WO Quantity', digits='Product Unit of Measure', copy=False)
    qty_output_prev_wo = fields.Float(
        'Previous WO Quantity', digits='Product Unit of Measure',
        compute="_compute_prev_work_order")
    prev_work_order_id = fields.Many2one(
        'mrp.workorder', 'Previous Work Order',
        compute="_compute_prev_work_order")
    milestone = fields.Boolean(
        'Milestone', compute='_get_milestone', store=True, readonly=True,
        states={'ready': [('readonly', False)], 'pending': [('readonly', False)]},
        copy=True)
    sequence = fields.Integer(
        'Sequence', compute='_get_sequence', store=True, readonly=True,
        states={'ready': [('readonly', False)], 'pending': [('readonly', False)]},
        copy=True)
    hours_uom = fields.Many2one(
        'uom.uom', 'Hours', related='workcenter_id.hours_uom')
    wo_capacity_requirements = fields.Float(
        'WO Capacity Requirements', compute='_wo_capacity_requirement', store=True)
    overall_duration = fields.Float(
        'Overall Duration', compute='_compute_overall_duration', store=True)
    partial_quantity = fields.Float(string='Partial Quantity', readonly=True)
    total_produce_quantity = fields.Float(
        string='Total Produce Quantity', readonly=True)
    roll_line_ids = fields.One2many(
        'mrp.wo.roll.line', 'workorder_id', 'Roll Lines')
    prev_roll_line_ids = fields.One2many(
        'mrp.wo.roll.line', 'prev_work_order_id', 'Prev Roll Lines')
    x_additional = fields.Float('New Qty')

    # ── NEW fields ────────────────────────────────────────────────────────────

    semifin_journal_entry_id = fields.Many2one(
        'account.move',
        string='Semi-Finished Journal Entry',
        copy=False,
        readonly=True,
        help="Journal entry posted when this workorder completes and rolls "
             "move to the semi-finished rack (CR WIP / DR Semi-Fin). "
             "Reversed automatically when the next workorder starts.",
    )

    wip_amount_wo = fields.Float(
        string='WO WIP Amount',
        digits='Product Price',
        readonly=True,
        copy=False,
        help="Mirrors production.wip_amount at the time this workorder "
             "was completed. = mat_cost + var_cost + fixed_cost on MO.",
    )

    roll_wip_value = fields.Float(
        string='Roll WIP Value',
        digits='Product Price',
        compute='_compute_roll_wip_value',
        store=True,
        help="Sum of roll_wip_value across all roll lines at this workorder.",
    )

    roll_count = fields.Integer(
        string='Roll Count',
        compute='_compute_roll_count',
        store=True,
        help="Number of rolls produced at this workorder.",
    )

    @api.depends('roll_line_ids.roll_wip_value')
    def _compute_roll_wip_value(self):
        for wo in self:
            wo.roll_wip_value = sum(
                wo.roll_line_ids.mapped('roll_wip_value')
            )

    @api.depends('roll_line_ids')
    def _compute_roll_count(self):
        for wo in self:
            wo.roll_count = len(
                wo.roll_line_ids.mapped('roll_id').filtered(bool)
            )

    def action_view_rolls(self):
        """Smart button — open rolls produced at this workorder."""
        self.ensure_one()
        roll_ids = self.roll_line_ids.mapped('roll_id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rolls — %s' % (self.name or ''),
            'res_model': 'mrp.production.roll',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', roll_ids)],
            'context': {'default_workorder_id': self.id},
        }

    # ══════════════════════════════════════════════════════════════════════════
    # SEMI-FIN GL POSTING HELPERS
    # ══════════════════════════════════════════════════════════════════════════

    def _is_last_workorder(self):
        """
        Return True if this workorder has the highest sequence in the MO.
        The last workorder (Sheeting) does NOT post a Semi-Fin entry —
        the FG receipt stock move handles CR WIP / DR FG automatically.
        """
        self.ensure_one()
        all_sequences = self.production_id.workorder_ids.mapped('sequence')
        if not all_sequences:
            return True
        return self.sequence == max(all_sequences)

    def _is_first_workorder(self):
        """
        Return True if this workorder has the lowest sequence in the MO.
        First workorder uses AVCO from stock.quant for material cost.
        Subsequent workorders carry forward from previous roll value.
        """
        self.ensure_one()
        all_sequences = self.production_id.workorder_ids.mapped('sequence')
        if not all_sequences:
            return True
        return self.sequence == min(all_sequences)

    def _get_wip_account(self):
        """
        Return the WIP GL account (e.g. 01-103322 WIP Excel) from the
        finished product's category (wip_account_id or
        x_property_account_inventory_categ_id field on product.category).
        """
        self.ensure_one()
        categ = self.production_id.product_id.categ_id
        wip_account = (
            getattr(categ, 'wip_account_id', False)
            or getattr(categ, 'x_property_account_inventory_categ_id', False)
        )
        if not wip_account:
            raise UserError(_(
                "No WIP account found on product category '%s'. "
                "Please set the WIP account on the product category."
            ) % categ.name)
        return wip_account

    def _get_semifin_account(self):
        """
        Return the Semi-Finished GL account (e.g. 01-103422 Semi Fin Excel)
        from the finished product's category.
        Uses property_stock_account_input_categ_id (Stock Input Account)
        which is already set to 01-103422 on the finished product category.
        """
        self.ensure_one()
        categ = self.production_id.product_id.categ_id
        semifin_account = getattr(
            categ, 'property_stock_account_input_categ_id', False)
        if not semifin_account:
            raise UserError(_(
                "No Stock Input account found on product category '%s'. "
                "Please set the Stock Input account on the product category."
            ) % categ.name)
        return semifin_account

    def _get_accumulated_wip_cost(self):
        """
        Return the total accumulated WIP cost on the MO at this point.
        Uses wip_amount which is already a stored computed field on
        mrp.production:
            wip_amount = mat_cost + var_cost + fixed_cost (when MO not done)
        This is always correct at workorder completion because the MO
        state is still 'in progress' at that point.
        """
        self.ensure_one()
        wip = self.production_id.wip_amount
        _logger.info(
            "WO %s: wip_amount=%s from MO %s",
            self.name, wip, self.production_id.name,
        )
        return wip

    def _get_wo_labour_ovh_cost(self):
        """
        Return total labour + overhead cost for THIS workorder only.
        Uses same duration logic as mrp_actual_posting.py:
        - If overall_duration is set → use working_duration
        - Otherwise → use duration
        """
        self.ensure_one()
        total_duration = 0.0
        for time in self.time_ids:
            if time.overall_duration:
                total_duration += time.working_duration
            else:
                total_duration += time.duration
        wo_labour = round(
            total_duration * self.workcenter_id.labor_costs_hour / 60, 2)
        wo_overhead = round(
            total_duration * self.workcenter_id.overhead_costs_hour / 60, 2)
        total = round(wo_labour + wo_overhead, 2)
        _logger.info(
            "WO %s: duration=%s labour=%s overhead=%s total=%s",
            self.name, total_duration, wo_labour, wo_overhead, total,
        )
        return total

    def _get_chemical_cost(self, consumed_qty):
        """
        Calculate chemical material cost for this workorder based on BOM lines.

        Formula:
            chemical_cost = Σ (bom_line.product_qty / bom.product_qty)
                              × avco_per_lb
                              × consumed_qty

        Conditions for a BOM line to be included:
            1. product_uom_id.name in ('lb', 'lbs') — identifies chemical
            2. This workorder's operation_id is in bom_line.workcenter_capacities

        Multiple matching BOM lines are summed.
        """
        # ... rest of code
        self.ensure_one()
        chemical_cost = 0.0

        bom = self.production_id.bom_id
        _logger.info("WO %s: bom=%s", self.name, bom)
        if not bom:
            _logger.warning(
                "WO %s: no BOM found on MO %s — skipping chemical cost.",
                self.name, self.production_id.name,
            )
            return 0.0

        bom_qty = bom.product_qty or 1.0
        wo_operation = self.operation_id
        _logger.info("WO %s: wo_operation=%s", self.name, wo_operation)

        for bom_line in bom.bom_line_ids:
            uom_name = (bom_line.product_uom_id.name or '').lower().strip()
            _logger.info(
                "WO %s: bom_line=%s uom=%s workcenter_capacities=%s",
                self.name, bom_line.product_id.name, uom_name,
                bom_line.workcenter_capacities.mapped('name')
            )
            if uom_name not in ('lb', 'lbs'):
                _logger.info("WO %s: skipping — uom %s not lbs", self.name, uom_name)
                continue
            if wo_operation not in bom_line.workcenter_capacities:
                _logger.info(
                    "WO %s: skipping — operation %s not in capacities %s",
                    self.name, wo_operation.name,
                    bom_line.workcenter_capacities.mapped('name')
                )
                continue

            # ── Get AVCO of chemical product ─────────────────────────────
            product = bom_line.product_id
            quants = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('location_id.usage', '=', 'internal'),
                ('quantity', '>', 0),
            ])

            if not quants:
                _logger.warning(
                    "WO %s: no stock.quant found for chemical %s — skipping.",
                    self.name, product.name,
                )
                continue

            total_qty = sum(quants.mapped('quantity'))
            total_val = sum(quants.mapped('value'))

            if not total_qty:
                continue

            avco_per_lb = total_val / total_qty

            # ── Calculate chemical cost ───────────────────────────────────
            # (lbs in BOM / yds in BOM) × avco_per_lb × consumed_yds
            ratio = bom_line.product_qty / bom_qty
            line_cost = round(ratio * avco_per_lb * (consumed_qty or 0.0), 2)
            chemical_cost += line_cost

            _logger.info(
                "WO %s: chemical %s — bom_qty=%s bom_yds=%s "   
                "avco=%s consumed=%s ratio=%s cost=%s",
                self.name, product.name,
                bom_line.product_qty, bom_qty,
                avco_per_lb, consumed_qty, ratio, line_cost,
            )

        _logger.info(
            "WO %s: total chemical cost=%s for consumed=%s",
            self.name, chemical_cost, consumed_qty,
        )
        return chemical_cost


    def _get_roll_material_value_first_wo(self, roll_line):
        """
        For the FIRST workorder:
        Material value = Σ (AVCO per unit × consumed_qty)
        for each input roll (prev_roll_id).

        Steps:
        1. Get lot from prev_roll_id.lot_id
           If not set, search by roll name in stock.production.lot
           and persist the link on the roll object
        2. Find validated pick components transfer for this MO
           to get exact location where roll was delivered
        3. Get AVCO from stock.quant at that location
        4. Multiply by consumed_qty
        """
        self.ensure_one()
        material_value = 0.0

        output_roll_lines = self.roll_line_ids.filtered(
            lambda l: l.roll_id == roll_line.roll_id
        )

        for line in output_roll_lines:
            if not line.prev_roll_id:
                continue

            # ── Step 1: Get or find lot ───────────────────────────────────
            lot = line.prev_roll_id.lot_id
            if not lot:
                lot = self.env['stock.production.lot'].search([
                    ('name', '=', line.prev_roll_id.name),
                ], limit=1)
                if lot:
                    line.prev_roll_id.lot_id = lot
                    _logger.info(
                        "WO %s: linked lot %s to roll %s",
                        self.name, lot.name, line.prev_roll_id.name,
                    )

            if not lot:
                _logger.warning(
                    "WO %s: no lot found for roll %s — skipping.",
                    self.name, line.prev_roll_id.name,
                )
                continue

            # ── Step 2: Find location from validated picking ──────────────
            location = False
            done_pickings = self.production_id.picking_ids.filtered(
                lambda p: p.state == 'done'
            )
            for picking in done_pickings:
                move_line = picking.move_line_ids.filtered(
                    lambda ml: ml.lot_id == lot
                )
                if move_line:
                    location = move_line[0].location_dest_id
                    break

            # ── Step 3: Get AVCO from stock.quant ────────────────────────
            quant = False
            if location:
                quant = self.env['stock.quant'].search([
                    ('lot_id', '=', lot.id),
                    ('product_id', '=', lot.product_id.id),
                    ('location_id', '=', location.id),
                    ('quantity', '>', 0),
                ], limit=1)

            # Fallback: sum across all internal locations
            if not quant:
                quants = self.env['stock.quant'].search([
                    ('lot_id', '=', lot.id),
                    ('product_id', '=', lot.product_id.id),
                    ('location_id.usage', '=', 'internal'),
                    ('quantity', '>', 0),
                ])
                if quants:
                    total_qty = sum(quants.mapped('quantity'))
                    total_val = sum(quants.mapped('value'))
                    if total_qty:
                        cost_per_unit = total_val / total_qty
                        line_material = round(
                            cost_per_unit * (line.consumed_qty or 0.0), 2)
                        material_value += line_material
                        _logger.info(
                            "WO %s: roll %s lot %s (fallback all locations) — "
                            "cost/unit=%s consumed=%s material=%s",
                            self.name, line.prev_roll_id.name, lot.name,
                            cost_per_unit, line.consumed_qty, line_material,
                        )
                continue

            if not quant.quantity:
                _logger.warning(
                    "WO %s: quant qty zero for lot %s", self.name, lot.name)
                continue

            # ── Step 4: Calculate ─────────────────────────────────────────
            cost_per_unit = quant.value / quant.quantity
            line_material = round(
                cost_per_unit * (line.consumed_qty or 0.0), 2)
            material_value += line_material

            # ── Step 5: Add chemical cost from BOM ───────────────────────────
            # Uses consumed_qty from the representative roll line
            consumed = roll_line.consumed_qty or 0.0
            chemical = self._get_chemical_cost(consumed)
            material_value += chemical
            _logger.info(
                "WO %s: roll %s — lot_material=%s chemical=%s total_material=%s",
                self.name,
                getattr(roll_line.roll_id, 'name', ''),
                material_value - chemical,
                chemical,
                material_value,
            )
            # ─────────────────────────────────────────────────────────────────

            _logger.info(
                "WO %s: roll %s lot %s location %s — "
                "cost/unit=%s consumed=%s material=%s",
                self.name, line.prev_roll_id.name, lot.name,
                location.name if location else 'unknown',
                cost_per_unit, line.consumed_qty, line_material,
            )

        return material_value

    def _get_roll_material_value_subsequent_wo(self, roll_line):
        """
        For SUBSEQUENT workorders (Embossing, Sheeting):
        Material value = prev_roll_line.roll_wip_value
                         × (consumed_qty / prev_roll_line.quantity)

        Carries forward the fully loaded cost from the previous
        workorder's roll line proportional to yards consumed.
        """
        self.ensure_one()
        material_value = 0.0

        # Get all roll lines for this output roll
        output_roll_lines = self.roll_line_ids.filtered(
            lambda l: l.roll_id == roll_line.roll_id
        )

        for line in output_roll_lines:
            if not line.prev_roll_id:
                continue

            # Find the previous WO roll line for this input roll
            prev_roll_line = self.prev_roll_line_ids.filtered(
                lambda l: l.roll_id == line.prev_roll_id
            )

            if not prev_roll_line:
                _logger.warning(
                    "WO %s: no prev_roll_line found for input roll %s",
                    self.name, line.prev_roll_id.name,
                )
                continue

            prev_wip = prev_roll_line[0].roll_wip_value
            prev_qty = prev_roll_line[0].quantity or 0.0

            if not prev_qty:
                _logger.warning(
                    "WO %s: prev roll line qty is zero for roll %s",
                    self.name, line.prev_roll_id.name,
                )
                continue

            consumed = line.consumed_qty or 0.0
            line_material = round(prev_wip * (consumed / prev_qty), 2)
            material_value += line_material

            _logger.info(
                "WO %s: carry forward roll %s — "
                "prev_wip=%s prev_qty=%s consumed=%s material=%s",
                self.name, line.prev_roll_id.name,
                prev_wip, prev_qty, consumed, line_material,
            )

        return material_value

    def _compute_roll_cost_split(self):
        """
        """
        self.ensure_one()

        roll_lines = self.roll_line_ids
        if not roll_lines:
            _logger.warning(
                "WO %s: no roll lines found, skipping roll cost split.",
                self.name,
            )
            return False

        # Store WIP amount snapshot on workorder
        self.wip_amount_wo = self.production_id.wip_amount

        # Determine if this is the first workorder by sequence
        is_first = self._is_first_workorder()

        # Total labour + overhead for this WO
        wo_lab_ovh = self._get_wo_labour_ovh_cost()

        # ── Group ALL lines by output roll_id ─────────────────────────────────
        # Key: mrp.production.roll record
        # Value: list of mrp.wo.roll.line records for that output roll
        #
        # This supports the case where multiple input rolls (prev_roll_id A and B)
        # are combined into a single output roll (roll_id X).
        # In that case roll_id X has two lines — one per input source.
        output_roll_groups = {}
        for line in roll_lines:
            key = line.roll_id
            if key not in output_roll_groups:
                output_roll_groups[key] = []
            output_roll_groups[key].append(line)

        # Total yards across all output rolls (sum per roll, then sum of rolls)
        # Uses the max quantity seen per line group as the roll's produced yards.
        # When multiple lines share a roll_id, their quantities are additive
        # (each line represents yards consumed from a different input source
        # that contributed to the same output roll).
        total_yards = 0.0
        roll_yards_map = {}  # roll → total yards for that roll
        for roll, lines in output_roll_groups.items():
            roll_yards = sum(l.quantity or 0.0 for l in lines)
            roll_yards_map[roll] = roll_yards
            total_yards += roll_yards

        if not total_yards:
            _logger.warning(
                "WO %s: total yards is zero, skipping roll cost split.",
                self.name,
            )
            return False

        _logger.info(
            "WO %s: computing roll cost split — "
            "is_first=%s wo_lab_ovh=%s total_yards=%s rolls=%s",
            self.name, is_first, wo_lab_ovh, total_yards,
            len(output_roll_groups),
        )

        roll_list = list(output_roll_groups.items())
        allocated_lab_ovh = 0.0

        for i, (roll, lines) in enumerate(roll_list):
            roll_yards = roll_yards_map[roll]

            # ── Labour + Overhead (proportional by yards) ─────────────────────
            if i < len(roll_list) - 1:
                lab_ovh = round(wo_lab_ovh * (roll_yards / total_yards), 2)
            else:
                # Last roll gets remainder to avoid rounding gap
                lab_ovh = round(wo_lab_ovh - allocated_lab_ovh, 2)
            allocated_lab_ovh += lab_ovh

            # ── Material value ────────────────────────────────────────────────
            # Sum material cost across ALL input lines for this output roll.
            # Each line may have a different prev_roll_id (different input source).
            mat = 0.0
            # Use the first line as representative for the helper signature,
            # but the helpers internally iterate all lines for this roll_id.
            rep_line = lines[0]
            if is_first:
                mat = self._get_roll_material_value_first_wo(rep_line)
            else:
                mat = self._get_roll_material_value_subsequent_wo(rep_line)

            # ── Total roll WIP value ──────────────────────────────────────────
            total_val = round(mat + lab_ovh, 2)

            # Write to ALL roll lines for this output roll
            output_roll_lines = self.env['mrp.wo.roll.line'].browse(
                [l.id for l in lines]
            )
            for line in output_roll_lines:
                line.write({
                    'roll_material_value': mat,
                    'roll_labour_ovh_value': lab_ovh,
                    'roll_wip_value': total_val,
                })

            # Update mrp.production.roll for visibility
            if roll:
                roll.roll_wip_value = total_val
                roll.roll_material_value = mat
                # Set original_wip_value only once — never overwrite
                # Used as basis for remaining value when roll is consumed
                # at subsequent workorders
                if not roll.original_wip_value:
                    roll.original_wip_value = total_val

            _logger.info(
                "WO %s: Roll %s — yards=%s mat=%s lab_ovh=%s total=%s "
                "input_lines=%s",
                self.name,
                getattr(roll, 'name', roll.id),
                roll_yards, mat, lab_ovh, total_val,
                len(lines),
            )

        return True

    # def _compute_roll_cost_split(self):
    #     """
    #     Calculate and store roll_material_value, roll_labour_ovh_value,
    #     and roll_wip_value on each roll line in roll_line_ids.
 
    #     Also:
    #     - Updates wip_amount_wo on this workorder
    #     - Updates roll_wip_value on mrp.production.roll for visibility
    #     - Posts/updates Semi-Fin journal entry per roll
 
    #     Called from:
    #     - add_roll_lines() in roll_line_wizard.py (preliminary)
    #     - button_finish() (final correction)
    #     """
    #     self.ensure_one()
 
    #     roll_lines = self.roll_line_ids
    #     if not roll_lines:
    #         _logger.warning(
    #             "WO %s: no roll lines found, skipping roll cost split.",
    #             self.name,
    #         )
    #         return False
 
    #     # Store WIP amount snapshot on workorder
    #     self.wip_amount_wo = self.production_id.wip_amount
 
    #     # Determine if this is the first workorder by sequence
    #     is_first = self._is_first_workorder()
 
    #     # Total labour + overhead for this WO
    #     wo_lab_ovh = self._get_wo_labour_ovh_cost()
 
    #     # Group roll lines by output roll_id
    #     # (multiple input lines can feed one output roll)
    #     output_rolls = {}
    #     for line in roll_lines:
    #         if line.roll_id not in output_rolls:
    #             output_rolls[line.roll_id] = line
 
    #     # Total yards across all output rolls
    #     total_yards = sum(
    #         line.quantity or 0.0
    #         for line in output_rolls.values()
    #     )
 
    #     if not total_yards:
    #         _logger.warning(
    #             "WO %s: total yards is zero, skipping roll cost split.",
    #             self.name,
    #         )
    #         return False
 
    #     _logger.info(
    #         "WO %s: computing roll cost split — "
    #         "is_first=%s wo_lab_ovh=%s total_yards=%s rolls=%s",
    #         self.name, is_first, wo_lab_ovh, total_yards,
    #         len(output_rolls),
    #     )
 
    #     lines_list = list(output_rolls.values())
    #     allocated_lab_ovh = 0.0
 
    #     for i, (roll, rep_line) in enumerate(output_rolls.items()):
    #         roll_yards = rep_line.quantity or 0.0
 
    #         # ── Labour + Overhead (proportional by yards) ─────────────────
    #         if i < len(lines_list) - 1:
    #             lab_ovh = round(wo_lab_ovh * (roll_yards / total_yards), 2)
    #         else:
    #             # Last roll gets remainder to avoid rounding gap
    #             lab_ovh = round(wo_lab_ovh - allocated_lab_ovh, 2)
    #         allocated_lab_ovh += lab_ovh
 
    #         # ── Material value ────────────────────────────────────────────
    #         if is_first:
    #             # First WO: fetch AVCO from stock.quant via lot
    #             mat = self._get_roll_material_value_first_wo(rep_line)
    #         else:
    #             # Subsequent WOs: carry forward from previous roll
    #             mat = self._get_roll_material_value_subsequent_wo(rep_line)
 
    #         # ── Total roll WIP value ──────────────────────────────────────
    #         total_val = round(mat + lab_ovh, 2)
 
    #         # Write to all roll lines for this output roll
    #         output_roll_lines = roll_lines.filtered(
    #             lambda l: l.roll_id == roll
    #         )
    #         for line in output_roll_lines:
    #             line.write({
    #                 'roll_material_value': mat,
    #                 'roll_labour_ovh_value': lab_ovh,
    #                 'roll_wip_value': total_val,
    #             })
 
    #         # Update mrp.production.roll for visibility
    #         if roll:
    #             roll.roll_wip_value = total_val
    #             roll.roll_material_value = mat 
    #             # Set original_wip_value only once — never overwrite
    #             # This is used as basis for remaining value calculation
    #             # when roll is consumed at subsequent workorders
    #             if not roll.original_wip_value:
    #                 roll.original_wip_value = total_val
 
    #         _logger.info(
    #             "WO %s: Roll %s — yards=%s mat=%s lab_ovh=%s total=%s",
    #             self.name,
    #             getattr(roll, 'name', roll.id),
    #             roll_yards, mat, lab_ovh, total_val,
    #         )
 
    #     return True
    # def _compute_roll_cost_split(self):
    #     """
    #     Calculate and store roll_material_value, roll_labour_ovh_value,
    #     and roll_wip_value on each roll line in roll_line_ids.

    #     Also:
    #     - Updates wip_amount_wo on this workorder
    #     - Updates roll_wip_value on mrp.production.roll for visibility
    #     - Posts/updates Semi-Fin journal entry per roll

    #     Called from:
    #     - add_roll_lines() in roll_line_wizard.py (preliminary)
    #     - button_finish() (final correction)
    #     """
    #     self.ensure_one()

    #     roll_lines = self.roll_line_ids
    #     if not roll_lines:
    #         _logger.warning(
    #             "WO %s: no roll lines found, skipping roll cost split.",
    #             self.name,
    #         )
    #         return False

    #     # Store WIP amount snapshot on workorder
    #     self.wip_amount_wo = self.production_id.wip_amount

    #     # Determine if this is the first workorder by sequence
    #     is_first = self._is_first_workorder()

    #     # Total labour + overhead for this WO
    #     wo_lab_ovh = self._get_wo_labour_ovh_cost()

    #     # Group roll lines by output roll_id
    #     # (multiple input lines can feed one output roll)
    #     output_rolls = {}
    #     for line in roll_lines:
    #         if line.roll_id not in output_rolls:
    #             output_rolls[line.roll_id] = line

    #     # Total yards across all output rolls
    #     total_yards = sum(
    #         line.quantity or 0.0
    #         for line in output_rolls.values()
    #     )

    #     if not total_yards:
    #         _logger.warning(
    #             "WO %s: total yards is zero, skipping roll cost split.",
    #             self.name,
    #         )
    #         return False

    #     _logger.info(
    #         "WO %s: computing roll cost split — "
    #         "is_first=%s wo_lab_ovh=%s total_yards=%s rolls=%s",
    #         self.name, is_first, wo_lab_ovh, total_yards,
    #         len(output_rolls),
    #     )

    #     lines_list = list(output_rolls.values())
    #     allocated_lab_ovh = 0.0

    #     for i, (roll, rep_line) in enumerate(output_rolls.items()):
    #         roll_yards = rep_line.quantity or 0.0

    #         # ── Labour + Overhead (proportional by yards) ─────────────────
    #         if i < len(lines_list) - 1:
    #             lab_ovh = round(wo_lab_ovh * (roll_yards / total_yards), 2)
    #         else:
    #             # Last roll gets remainder to avoid rounding gap
    #             lab_ovh = round(wo_lab_ovh - allocated_lab_ovh, 2)
    #         allocated_lab_ovh += lab_ovh

    #         # ── Material value ────────────────────────────────────────────
    #         if is_first:
    #             # First WO: fetch AVCO from stock.quant via lot
    #             mat = self._get_roll_material_value_first_wo(rep_line)
    #         else:
    #             # Subsequent WOs: carry forward from previous roll
    #             mat = self._get_roll_material_value_subsequent_wo(rep_line)

    #         # ── Total roll WIP value ──────────────────────────────────────
    #         total_val = round(mat + lab_ovh, 2)

    #         # Write to all roll lines for this output roll
    #         output_roll_lines = roll_lines.filtered(
    #             lambda l: l.roll_id == roll
    #         )
    #         for line in output_roll_lines:
    #             line.with_context(
    #                 skip_remained_update=True,
    #                 no_recompute=True,
    #             ).write({
    #                 'roll_material_value': mat,
    #                 'roll_labour_ovh_value': lab_ovh,
    #                 'roll_wip_value': total_val,
    #             })
    #             if line.workorder_id and line.workorder_id.next_work_order_id:
    #                 line.with_context(skip_remained_update=True).write({
    #                     'prev_work_order_id': line.workorder_id.next_work_order_id.id
    #                 })
    #                     # for line in output_roll_lines:
    #         #     line.write({
    #         #         'roll_material_value': mat,
    #         #         'roll_labour_ovh_value': lab_ovh,
    #         #         'roll_wip_value': total_val,
    #         #     })

    #         # Update mrp.production.roll for visibility
    #         if roll:
    #             roll.with_context(skip_remained_update=True).write({
    #                 'roll_wip_value': total_val
    #             })
    #         # if roll:
    #         #     roll.roll_wip_value = total_val

    #         _logger.info(
    #             "WO %s: Roll %s — yards=%s mat=%s lab_ovh=%s total=%s",
    #             self.name,
    #             getattr(roll, 'name', roll.id),
    #             roll_yards, mat, lab_ovh, total_val,
    #         )

    #     return True

    def _post_semifin_journal_entry(self):
        """
        Post Semi-Fin journal entry per roll when a non-last workorder
        completes and rolls are returned to the storage rack.

        For each roll line:
            CR  WIP Excel     (01-103322)   ← roll leaving WIP
            DR  Semi-Fin      (01-103422)   ← roll arriving at rack

        Amount per roll = roll_line.roll_wip_value
        One journal entry per roll, stored on roll_line.roll_journal_entry_id.

        If a previous entry exists for a roll (preliminary from Add button),
        it is reversed and a new entry is posted with the final value.
        """
        self.ensure_one()

        if not self.roll_line_ids:
            _logger.warning(
                "WO %s: no roll lines, skipping Semi-Fin posting.", self.name)
            return False

        wip_account = self._get_wip_account()
        semifin_account = self._get_semifin_account()
        journal = self.production_id.company_id.manufacturing_journal_id

        if not journal:
            raise UserError(_(
                "Manufacturing Journal is not defined on Company '%s'."
            ) % self.production_id.company_id.name)

        # Group by output roll — post one entry per roll
        output_rolls = {}
        for line in self.roll_line_ids:
            if line.roll_id and line.roll_id not in output_rolls:
                output_rolls[line.roll_id] = line

        for roll, rep_line in output_rolls.items():
            amount = rep_line.roll_wip_value
            if not amount or amount <= 0.0:
                _logger.warning(
                    "WO %s: Roll %s has zero value, skipping.",
                    self.name, roll.name,
                )
                continue

            # Reverse existing entry if present (preliminary correction)
            if rep_line.roll_journal_entry_id:
                prev_move = rep_line.roll_journal_entry_id
                if prev_move.state != 'cancel':
                    existing_reversal = self.env['account.move'].search([
                        ('reversed_entry_id', '=', prev_move.id),
                        ('state', '!=', 'cancel'),
                    ], limit=1)
                    if not existing_reversal:
                        reversal_wizard = self.env[
                            'account.move.reversal'
                        ].with_context(
                            active_ids=prev_move.ids,
                            active_model='account.move',
                        ).create({
                            'date': fields.Date.today(),
                            'reason': 'Roll value correction',
                            'refund_method': 'cancel',
                            'journal_id': prev_move.journal_id.id,
                        })
                        reversal_wizard.reverse_moves()
                        _logger.info(
                            "WO %s: Roll %s — reversed preliminary entry %s",
                            self.name, roll.name, prev_move.name,
                        )

            desc = "%s - %s - Roll %s to Rack" % (
                self.production_id.name or '',
                self.name or '',
                roll.name or '',
            )

            move = self.env['account.move'].create({
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'ref': desc,
                'company_id': self.production_id.company_id.id,
            })

            # CR WIP Excel
            self.env['account.move.line'].with_context(
                check_move_validity=False
            ).create({
                'move_id': move.id,
                'account_id': wip_account.id,
                'name': desc,
                'product_id': self.production_id.product_id.id,
                'quantity': rep_line.quantity,
                'product_uom_id': self.production_id.product_uom_id.id,
                'credit': amount,
                'debit': 0.0,
                'manufacture_order_id': self.production_id.id,
            })

            # DR Semi-Fin Excel
            self.env['account.move.line'].with_context(
                check_move_validity=False
            ).create({
                'move_id': move.id,
                'account_id': semifin_account.id,
                'name': desc,
                'product_id': self.production_id.product_id.id,
                'quantity': rep_line.quantity,
                'product_uom_id': self.production_id.product_uom_id.id,
                'credit': 0.0,
                'debit': amount,
                'manufacture_order_id': self.production_id.id,
            })

            move.post()

            # Store on all lines for this output roll
            self.roll_line_ids.filtered(
                lambda l: l.roll_id == roll
            ).write({'roll_journal_entry_id': move.id})

            _logger.info(
                "WO %s: Roll %s — Semi-Fin entry posted move=%s amount=%s",
                self.name, roll.name, move.name, amount,
            )

        return True

    def _reverse_semifin_journal_entry(self):
        """
        Reverse all previous workorder's per-roll Semi-Fin entries
        when this workorder starts (operator picks up rolls from rack):

            CR  Semi-Fin      (01-103422)   ← rolls leaving rack
            DR  WIP Excel     (01-103322)   ← rolls entering WIP again

        Finds previous WO roll lines that have roll_journal_entry_id set
        and reverses each one. Guard prevents double reversal.
        """
        self.ensure_one()

        # Find previous workorder by sequence
        ordered = self.production_id.workorder_ids.sorted(
            lambda w: (w.sequence, w.id)
        )
        prev_wo = False
        for i, wo in enumerate(ordered):
            if wo.id == self.id and i > 0:
                prev_wo = ordered[i - 1]
                break

        if not prev_wo:
            _logger.info(
                "WO %s: first workorder, no Semi-Fin reversal needed.",
                self.name,
            )
            return False

        # Get all roll lines from previous WO that have journal entries
        prev_lines_with_entries = prev_wo.roll_line_ids.filtered(
            lambda l: l.roll_journal_entry_id
            and l.roll_journal_entry_id.state != 'cancel'
        )

        if not prev_lines_with_entries:
            _logger.info(
                "WO %s: no Semi-Fin entries found on prev WO %s.",
                self.name, prev_wo.name,
            )
            return False

        # Get unique journal entries (one per roll)
        unique_entries = prev_lines_with_entries.mapped(
            'roll_journal_entry_id'
        )

        desc = "%s - %s - Rolls from Rack" % (
            self.production_id.name or '',
            self.name or '',
        )

        for entry in unique_entries:
            # Guard: skip if already reversed
            existing_reversal = self.env['account.move'].search([
                ('reversed_entry_id', '=', entry.id),
                ('state', '!=', 'cancel'),
            ], limit=1)
            if existing_reversal:
                _logger.info(
                    "WO %s: entry %s already reversed, skipping.",
                    self.name, entry.name,
                )
                continue

            reversal_wizard = self.env['account.move.reversal'].with_context(
                active_ids=entry.ids,
                active_model='account.move',
            ).create({
                'date': fields.Date.today(),
                'reason': desc,
                'refund_method': 'cancel',
                'journal_id': entry.journal_id.id,
            })
            reversal_wizard.reverse_moves()

            _logger.info(
                "WO %s: reversed Semi-Fin entry %s from prev WO %s",
                self.name, entry.name, prev_wo.name,
            )

        return True

    # ══════════════════════════════════════════════════════════════════════════
    # EXISTING HELPERS (unchanged)
    # ══════════════════════════════════════════════════════════════════════════

    def _get_next_workorder(self):
        """Return the next workorder in sequence, or False if last."""
        self.ensure_one()
        ordered = self.production_id.workorder_ids.sorted(
            lambda w: (w.sequence, w.id))
        for i, wo in enumerate(ordered):
            if wo.id == self.id and i + 1 < len(ordered):
                return ordered[i + 1]
        return False

    def _get_default_wip_dest(self):
        """Return destination WIP location: next WO location if exists,
        else product production location."""
        self.ensure_one()
        nxt = self._get_next_workorder()
        if nxt and nxt.workcenter_id and nxt.workcenter_id.location_id:
            return nxt.workcenter_id.location_id
        prop = getattr(
            self.production_id.product_id, 'property_stock_production', False)
        return prop or False

    @staticmethod
    def _extract_roll_move_data(line):
        """Return quantity and lot (if any) for a roll output line."""
        _logger.info(
            "_extract_roll_move_data: line=%s fields=%s roll_id=%s",
            line, list(line._fields.keys()),
            getattr(line, 'roll_id', 'NO_FIELD')
        )
        qty = 0.0
        for field_name in (
            'remained_qty',
            'total_qty',
            'yards_qty',
            'quantity',
            'partial_done_qty',
        ):
            if hasattr(line, field_name):
                value = getattr(line, field_name) or 0.0
                if value:
                    qty = value
                    break

        lot = False
        lot_fields = ('lot_id', 'lot_producing_id', 'roll_id')
        for lot_field in lot_fields:
            if lot_field not in getattr(line, '_fields', {}):
                continue

            field_desc = line._fields[lot_field]
            if getattr(field_desc, 'type', False) != 'many2one':
                continue

            lot_record = getattr(line, lot_field, False)
            if not lot_record:
                continue

            if field_desc.comodel_name == 'stock.production.lot':
                lot = lot_record.id
                break

            for related_field in ('lot_id', 'lot_producing_id'):
                if related_field not in getattr(lot_record, '_fields', {}):
                    continue
                related_desc = lot_record._fields[related_field]
                if getattr(related_desc, 'type', False) != 'many2one':
                    continue
                if related_desc.comodel_name != 'stock.production.lot':
                    continue
                nested_lot = getattr(lot_record, related_field, False)
                if nested_lot:
                    lot = nested_lot.id
                    break

            if not lot and field_desc.comodel_name == 'mrp.production.roll':
                workorder = getattr(line, 'workorder_id', False)
                product = False
                company = False
                if workorder:
                    product = getattr(
                        workorder.production_id, 'product_id', False)
                    company = getattr(workorder, 'company_id', False)

                if lot_record.name and product:
                    lot_model = line.env['stock.production.lot']
                    existing_lot = lot_model.search([
                        ('name', '=', lot_record.name),
                        ('product_id', '=', product.id),
                        ('company_id', '=',
                         company.id if company else False),
                    ], limit=1)

                    if existing_lot:
                        lot = existing_lot.id
                    else:
                        lot_vals = {
                            'name': lot_record.name,
                            'product_id': product.id,
                            'company_id': company.id if company else False,
                        }
                        lot = lot_model.create(lot_vals).id

                    if 'lot_id' in getattr(lot_record, '_fields', {}):
                        lot_record.lot_id = lot
                    elif 'lot_producing_id' in getattr(
                            lot_record, '_fields', {}):
                        lot_record.lot_producing_id = lot

            if lot:
                break

        if not lot and 'roll_id' in getattr(
                line, '_fields', {}) and line.roll_id:
            lot_name = line.roll_id.name
            product = False
            company = False

            workorder = getattr(line, 'workorder_id', False)
            if workorder:
                product = getattr(
                    workorder.production_id, 'product_id', False)
                company = getattr(workorder, 'company_id', False)

            if lot_name and product:
                lot_model = line.env['stock.production.lot']
                existing_lot = lot_model.search([
                    ('name', '=', lot_name),
                    ('product_id', '=', product.id),
                    ('company_id', '=', company.id if company else False),
                ], limit=1)

                if existing_lot:
                    lot = existing_lot.id
                else:
                    lot_vals = {
                        'name': lot_name,
                        'product_id': product.id,
                        'company_id': company.id if company else False,
                    }
                    lot = lot_model.create(lot_vals).id

                if 'lot_id' in getattr(line.roll_id, '_fields', {}):
                    line.roll_id.lot_id = lot
                elif 'lot_producing_id' in getattr(
                        line.roll_id, '_fields', {}):
                    line.roll_id.lot_producing_id = lot

        return qty, lot

    def _create_pick_and_moves_for_output_rolls(
            self, pick_origin=None, lines=None):
        """Create one internal picking grouping the provided output roll lines.
        NOTE: Picking is left in 'assigned' state (not validated) intentionally
        so that NO stock valuation GL entries are posted for roll movements.
        GL entries are handled separately via _post_semifin_journal_entry().
        """
        self.ensure_one()

        RollLine = self.env['mrp.wo.roll.line']
        if lines is not None:
            output_lines = lines.filtered(
                lambda ln: ln._name == RollLine._name
                and getattr(ln, 'workorder_id', self) == self
            )
        else:
            output_lines = getattr(
                self, 'roll_line_ids', RollLine.browse())

        if not output_lines:
            _logger.debug(
                "No output roll lines for WO %s", self.id)
            return False

        src_loc = getattr(self.workcenter_id, 'location_id', False)
        dest_loc = self._get_default_wip_dest()
        if not src_loc or not dest_loc:
            raise UserError(_(
                "Missing source/destination WIP locations for workorder %s"
            ) % (self.name or self.id))

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'internal'),
            ('warehouse_id.company_id', '=', self.company_id.id)
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'internal')
            ], limit=1)
        if not picking_type:
            raise UserError(_(
                "No internal picking type found for company %s"
            ) % self.company_id.name)

        origin = pick_origin or (
            self.production_id.name or _('MO/%s') % self.production_id.id)
        pick_vals = {
            'picking_type_id': picking_type.id,
            'location_id': src_loc.id,
            'location_dest_id': dest_loc.id,
            'partner_id': (self.company_id.partner_id.id
                           if self.company_id.partner_id else False),
            'move_type': 'direct',
            'origin': origin,
            'company_id': self.company_id.id,
        }
        picking = self.env['stock.picking'].create(pick_vals)

        moves_created = []
        move_lot_map = {}

        for line in output_lines:
            qty, lot = self._extract_roll_move_data(line)
            if not qty or qty <= 0.0:
                continue

            product = self.production_id.product_id
            uom = self.production_id.product_uom_id

            move_vals = {
                'name': '%s: %s' % (
                    self.workcenter_id.name or '',
                    product.display_name),
                'product_id': product.id,
                'product_uom': uom.id,
                'product_uom_qty': qty,
                'company_id': self.company_id.id,
                'location_id': src_loc.id,
                'location_dest_id': dest_loc.id,
                'picking_id': picking.id,
                'origin': origin,
            }
            mv = self.env['stock.move'].create(move_vals)
            moves_created.append(mv)
            if lot:
                move_lot_map[mv.id] = lot

        if not moves_created:
            picking.unlink()
            return False

        # Intentionally left in 'assigned' — NOT validated
        # so no stock valuation entries are posted for roll movements
        picking.write({'state': 'assigned'})

        for mv in moves_created:
            lot = move_lot_map.get(mv.id)
            product = self.production_id.product_id
            uom = self.production_id.product_uom_id

            mv.write({'state': 'assigned'})
            mv.move_line_ids.unlink()

            self.env['stock.move.line'].create({
                'move_id': mv.id,
                'picking_id': picking.id,
                'product_id': product.id,
                'product_uom_qty': mv.product_uom_qty,
                'qty_done': 0.0,
                'product_uom_id': uom.id,
                'location_id': src_loc.id,
                'location_dest_id': dest_loc.id,
                'lot_id': lot or False,
            })

        return picking

    def action_create_roll_pickings_and_transfer(self):
        """Public action to create the picking for output rolls."""
        self.ensure_one()
        return self._create_pick_and_moves_for_output_rolls()

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS (unchanged)
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends('duration')
    def _compute_duration_hours(self):
        for wo in self:
            wo.duration_hours = round(wo.duration / 60.0, 2)

    @api.depends('operation_id.milestone')
    def _get_milestone(self):
        for workorder in self:
            if workorder.operation_id and workorder.operation_id.milestone:
                workorder.milestone = True
        return True

    @api.depends('operation_id.sequence')
    def _get_sequence(self):
        for workorder in self:
            if workorder.operation_id and workorder.operation_id.sequence:
                workorder.sequence = workorder.operation_id.sequence
        return True

    @api.depends('time_ids.overall_duration')
    def _compute_overall_duration(self):
        for workorder in self:
            workorder.overall_duration = sum(
                workorder.time_ids.mapped('overall_duration'))
        return True

    @api.depends('duration_expected')
    def _wo_capacity_requirement(self):
        for workorder in self:
            workorder.wo_capacity_requirements = (
                workorder.duration_expected) / 60
        return True

    @api.depends('state')
    def _compute_prev_work_order(self):
        for workorder in self:
            workorder.prev_work_order_id = False
            workorder.qty_output_prev_wo = 0
        return True

    @api.depends('time_ids', 'state')
    def _compute_dates_actual(self):
        date_start = False
        date_end = False
        for workorder in self:
            if workorder.state == 'done' and workorder.time_ids:
                date_start = workorder.time_ids.sorted(
                    'date_start')[0].date_start
                date_end = workorder.time_ids.sorted(
                    'date_end')[-1].date_end
            workorder.date_actual_start_wo = date_start
            workorder.date_actual_finished_wo = date_end
        return True

    @api.onchange('time_ids')
    def onchange_produce_quantity(self):
        qty = 0.0
        for rec in self.time_ids:
            qty += rec.produce_quantity
        self.total_produce_quantity = qty

    # ══════════════════════════════════════════════════════════════════════════
    # BUTTON ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def button_start(self):
        """
        Override button_start to reverse the previous workorder's
        Semi-Fin journal entry when operator starts this workorder.

        This represents rolls being pulled from the rack back into production:
            CR  Semi-Fin Excel  (01-103422)
            DR  WIP Excel       (01-103322)
        """
        for workorder in self:
            workorder.re_arrange_pre_next_work_order()
            # Force recompute prev_work_order_id on all roll lines in this MO
            all_roll_lines = workorder.production_id.workorder_ids.mapped('roll_line_ids')
            if all_roll_lines:
                all_roll_lines._compute_prev_work_order()
            if workorder.x_pattern_wo:
                frame_id = self.env['mrp.frames'].search([
                    ('x_pattern_number', '=', workorder.x_pattern_wo.id)
                ])
                if frame_id:
                    frame_id.write({
                        'x_current_workorder': (
                            workorder.operation_id.name + '-'
                            + workorder.production_id.name),
                        'x_wo_date': datetime.now(),
                    })

            if workorder.qty_output_wo == 0.0:
                if not workorder.prev_work_order_id:
                    workorder.qty_output_wo = workorder.qty_production
                else:
                    workorder.qty_output_wo = workorder.qty_output_prev_wo

            if (any(move.product_qty > move.forecast_availability
                    for move in workorder.production_id.move_raw_ids)
                    and not workorder.workcenter_id.start_without_stock):
                raise UserError(_(
                    'It is not possible to start workorder '
                    'without components availability'))

            workorder.workorder_checks()

            # ── NEW: Reverse previous WO Semi-Fin entry ──────────────────────
            # Posts: CR Semi-Fin / DR WIP
            # Skipped automatically if this is the first workorder or
            # if previous WO has no Semi-Fin entry
            try:
                workorder._reverse_semifin_journal_entry()
            except Exception as e:
                _logger.exception(
                    "WO %s: Semi-Fin reversal failed (non-blocking): %s",
                    workorder.name, e,
                )
            # ─────────────────────────────────────────────────────────────────

        return super().button_start()

    def button_finish(self):
        """
        Override button_finish to post the Semi-Fin journal entry
        when a non-last workorder completes and rolls go to the rack:
            CR  WIP Excel       (01-103322)
            DR  Semi-Fin Excel  (01-103422)

        The last workorder (highest sequence = Sheeting) skips this —
        the FG receipt stock move handles CR WIP / DR FG automatically.
        """
        super().button_finish()
        for workorder in self:
            # Existing: clean up capacity records
            wo_capacity_ids = self.env['mrp.workcenter.capacity'].search([
                ('workorder_id', '=', workorder.id)
            ])
            wo_capacity_ids.unlink()

            # Existing: milestone logic
            if workorder.operation_id.milestone:
                workorders = workorder.production_id.workorder_ids
                sequence_milestone = workorder.operation_id.sequence
                prev_workorders = [
                    x for x in workorders
                    if x.operation_id.sequence < sequence_milestone
                ]
                if any(pw.state == 'progress' for pw in prev_workorders):
                    raise UserError(_('previous workorders in progress'))
                for prev_workorder in prev_workorders:
                    if prev_workorder.state in ('ready', 'pending'):
                        prev_workorder.state = 'cancel'
                    wo_capacity_id = self.env[
                        'mrp.workcenter.capacity'
                    ].search([
                        ('workorder_id', '=', prev_workorder.id)
                    ], limit=1)
                    if wo_capacity_id:
                        wo_capacity_id.unlink()

            # ── NEW: Roll cost split + Semi-Fin GL entry ──────────────────────
            # Step 1: Calculate final roll values (corrects preliminary values
            #         posted at Add button time)
            try:
                workorder._compute_roll_cost_split()
            except Exception as e:
                _logger.exception(
                    "WO %s: roll cost split failed (non-blocking): %s",
                    workorder.name, e,
                )

            # Step 2: Post/correct Semi-Fin GL entries per roll
            # Only for non-last workorders (Coating, Embossing)
            # Last workorder (Sheeting) → FG receipt handles CR WIP / DR FG
            if not workorder._is_last_workorder():
                try:
                    workorder._post_semifin_journal_entry()
                except Exception as e:
                    _logger.exception(
                        "WO %s: Semi-Fin posting failed (non-blocking): %s",
                        workorder.name, e,
                    )
            else:
                _logger.info(
                    "WO %s: last workorder — skipping Semi-Fin entry, "
                    "FG receipt will handle CR WIP / DR FG.",
                    workorder.name,
                )
            # ─────────────────────────────────────────────────────────────────

        return True

    # ══════════════════════════════════════════════════════════════════════════
    # OTHER EXISTING METHODS (unchanged)
    # ══════════════════════════════════════════════════════════════════════════

    def workorder_checks(self):
        for workorder in self:
            if not workorder.date_planned_start_wo:
                raise UserError(_('Manufacturing Order not scheduled yet'))
            if (workorder.qty_output_wo != workorder.qty_production
                    and not workorder.workcenter_id.partial_confirmation):
                raise UserError(_('partial confirmation is not allowed'))
            if workorder.operation_id.milestone:
                sequence_milestone = workorder.operation_id.sequence
                prev_workorders_closed = (
                    workorder.production_id.workorder_ids.filtered(
                        lambda x: (
                            x.operation_id.sequence < sequence_milestone
                            and x.state == 'done'
                        )
                    )
                )
                if prev_workorders_closed:
                    max_qty_output = min(
                        prev_workorders_closed.mapped('qty_output_wo'))
                    if workorder.qty_output_wo > max_qty_output:
                        raise UserError(_(
                            'It is not possible to produce more than %s'
                        ) % max_qty_output)
        return True

    @api.model
    def create(self, vals):
        rec = super(MrpWorkorder, self).create(vals)
        rec.re_arrange_pre_next_work_order()
        
        # Update prev_work_order_id on previous WO's existing roll lines
        ordered = rec.production_id.workorder_ids.sorted(
            lambda w: (w.sequence, w.id)
        )
        for i, wo in enumerate(ordered):
            if wo.id == rec.id and i > 0:
                prev_wo = ordered[i - 1]
                if prev_wo.roll_line_ids:
                    prev_wo.roll_line_ids.with_context(
                        skip_remained_update=True
                    ).write({
                        'prev_work_order_id': rec.id
                    })
                break
        
        return rec
    # @api.model
    # def create(self, vals):
    #     rec = super(MrpWorkorder, self).create(vals)
    #     rec.re_arrange_pre_next_work_order()
    #     return rec


    def re_arrange_pre_next_work_order(self):
        if self.production_id:
            wo_rec = self.search([
                ('production_id', '=', self.production_id.id)
            ], order="sequence")
            
            _logger.info("re_arrange: production=%s found WOs=%s",
                self.production_id.name,
                [(w.name, w.sequence) for w in wo_rec]
            )
            
            previous_workorder = False
            for wo in wo_rec:
                if not previous_workorder:
                    previous_workorder = wo
                    continue
                if previous_workorder:
                    wo.prev_work_order_id = previous_workorder.id
                    previous_workorder.next_work_order_id = wo  # ← FIXED
                    _logger.info("re_arrange: set %s.next_work_order_id = %s",
                        previous_workorder.name, wo.name)
                    previous_workorder = wo
            if wo_rec:
                wo_rec[-1].next_work_order_id = False
    # def re_arrange_pre_next_work_order(self):
    #     if self.production_id:
    #         wo_rec = self.search([
    #             ('production_id', '=', self.production_id.id)
    #         ], order="sequence")
    #         previous_workorder = False
    #         for wo in wo_rec:
    #             if not previous_workorder:
    #                 previous_workorder = wo
    #                 continue
    #             if previous_workorder:
    #                 wo.prev_work_order_id = previous_workorder.id
    #                 wo.prev_work_order_id.next_work_order_id = wo
    #                 previous_workorder = wo
    #         if wo_rec:
    #             wo_rec[-1].next_work_order_id = False

    def _get_capacity_load(self, start_date, end_date):
        _logger.info("ST DATET'%s'", start_date)
        _logger.info("EN DATTTEE'%s'", end_date)
        sdate = start_date.date()
        edate = end_date.date()
        delta = edate - sdate
        list_days = []
        nro_hours = 0.0
        cpp = 0.0
        list_days.append(start_date)
        for i in range(delta.days):
            day = sdate + timedelta(days=i + 1)
            day = datetime.combine(day, datetime.min.time())
            list_days.append(day)
        list_days.append(end_date)
        for i in range(len(list_days) - 1):
            for workorder in self:
                nro_hours = (
                    workorder.workcenter_id.resource_calendar_id
                    .get_work_duration_data(
                        list_days[i], list_days[i + 1])['hours']
                )
                cpp = (
                    workorder.operation_id.capacity
                    if workorder.operation_id.capacity
                    else workorder.workcenter_id.capacity
                )
                if nro_hours > 0:
                    self.env['mrp.workcenter.capacity'].create({
                        'workcenter_id': workorder.workcenter_id.id,
                        'workorder_id': workorder.id,
                        'product_id': workorder.production_id.product_id.id,
                        'product_qty': workorder.production_id.product_qty,
                        'available_capacity_yards': cpp,
                        'product_uom_id': (
                            workorder.production_id.product_uom_id.id),
                        'date_planned': list_days[i],
                        'wo_capacity_requirements': nro_hours,
                    })
        return True

    @api.constrains('date_planned_start_wo', 'date_planned_finished_wo')
    def _change_scheduled_dates(self):
        for workorder in self:
            date_planned_start = workorder.date_planned_start_wo
            date_planned_finish = workorder.date_planned_finished_wo
            if date_planned_start and date_planned_finish:
                user_tz = self.env.user.tz or 'UTC'
                user_timezone = timezone(user_tz)

                if date_planned_start.tzinfo is None:
                    date_planned_start = user_timezone.localize(
                        date_planned_start)
                else:
                    date_planned_start = date_planned_start.astimezone(
                        user_timezone)
                date_planned_start = date_planned_start.astimezone(
                    utc).replace(tzinfo=None)

                if date_planned_finish.tzinfo is None:
                    date_planned_finish = user_timezone.localize(
                        date_planned_finish)
                else:
                    date_planned_finish = date_planned_finish.astimezone(
                        user_timezone)
                date_planned_finish = date_planned_finish.astimezone(
                    utc).replace(tzinfo=None)

                wo_capacity_ids = self.env['mrp.workcenter.capacity'].search([
                    ('workorder_id', '=', workorder.id)
                ])
                wo_capacity_ids.unlink()
                workorder._get_capacity_load(
                    date_planned_start, date_planned_finish)
        return True

    def backwards_scheduling(self):
        for workorder in self:
            time_delta = workorder.duration_expected
            workorder.date_planned_start_wo = (
                workorder.date_planned_finished_wo
                - timedelta(minutes=time_delta)
            )
            if workorder.workcenter_id.resource_calendar_id:
                calendar = workorder.workcenter_id.resource_calendar_id
                duration_expected = -workorder.duration_expected / 60
                workorder.date_planned_start_wo = calendar.plan_hours(
                    duration_expected, workorder.date_planned_finished_wo, True)

    def forwards_scheduling(self):
        for workorder in self:
            time_delta = workorder.duration_expected
            workorder.date_planned_finished_wo = (
                workorder.date_planned_start_wo
                + timedelta(minutes=time_delta)
            )
            if workorder.workcenter_id.resource_calendar_id:
                calendar = workorder.workcenter_id.resource_calendar_id
                duration_expected = workorder.duration_expected / 60
                workorder.date_planned_finished_wo = calendar.plan_hours(
                    duration_expected, workorder.date_planned_start_wo, True)

    def _get_lot_consumed_at_prev_same_wc_wo(self, lot_name):
        ordered = self.production_id.workorder_ids.sorted(
            lambda w: (w.sequence, w.id))
        wo_list = list(ordered)
        for i, wo in enumerate(wo_list):
            if wo.id == self.id and i > 0:
                prev_wo = wo_list[i - 1]
                if prev_wo.workcenter_id == self.workcenter_id:
                    # Look at consumed_qty where the INPUT roll (prev_roll_id)
                    # matches the lot name — not the output roll name
                    consumed = sum(
                        line.consumed_qty or 0.0
                        for line in prev_wo.roll_line_ids
                        if line.prev_roll_id and line.prev_roll_id.name == lot_name
                    )
                    _logger.info(
                        "_get_lot_consumed_at_prev_same_wc_wo: "
                        "WO=%s prev_WO=%s lot=%s consumed=%s",
                        self.name, prev_wo.name, lot_name, consumed,
                    )
                    return consumed
        return 0.0

    def get_previous_rolls(self):
        """Batch-safe: populate prev_roll_line_ids from DONE pickings'
        lots for each WO."""
        precision = (
            self.env['decimal.precision'].precision_get(
                'Product Unit of Measure') or 2
        )

        def _process_one_wo(wo):
            allow_components = set()
            if wo.operation_id:
                for mv in wo.production_id.move_raw_ids:
                    op = getattr(mv.bom_line_id, 'operation_id', False)
                    if op and op.id == wo.operation_id.id:
                        allow_components.add(mv.product_id.id)

            if not allow_components:
                allow_components = {
                    mv.product_id.id
                    for mv in wo.production_id.move_raw_ids
                }

            _logger.info("get_previous_rolls WO=%s allow_components=%s",
                wo.name, allow_components)

            pickings = wo.production_id.picking_ids.filtered(
                lambda p: p.state == 'done')

            _logger.info("get_previous_rolls done pickings=%s",
                pickings.mapped('name'))

            if not pickings:
                return

            for picking in pickings:
                lines = (picking.move_line_ids_without_package
                         or picking.move_line_ids)

                _logger.info("picking=%s total lines=%s", picking.name, len(lines))

                lines = lines.filtered(
                    lambda ml: ml.product_id
                    and ml.product_id.id in allow_components
                )

                _logger.info("filtered lines=%s", len(lines))

                for ml in lines:
                    lot_name = (
                        (ml.lot_id and ml.lot_id.name) or ml.lot_name)

                    _logger.info("  ml product=%s lot=%s qty_done=%s",
                        ml.product_id.name,
                        lot_name or 'NO LOT',
                        ml.qty_done,
                    )

                    if not lot_name:
                        continue

                    qty_done = ml.qty_done or 0.0
                    # Deduct consumption at same-WC predecessor WO if applicable
                    deducted = wo._get_lot_consumed_at_prev_same_wc_wo(lot_name)
                    if deducted:
                        _logger.info(
                            "  deducting %s consumed at prev same-WC WO "
                            "from qty %s", deducted, qty_done,
                        )
                        qty_done = max(qty_done - deducted, 0.0)
                    if float_compare(
                            qty_done, 0.0,
                            precision_digits=precision) <= 0:
                        _logger.info("  skipping — qty_done=0 after deduction")
                        continue

                    exists = wo.prev_roll_line_ids.filtered(
                        lambda l: l.roll_id
                        and l.roll_id.name == lot_name
                    )
                    if exists:
                        # Update qty in case deduction changed it
                        exists[0].quantity = qty_done
                        _logger.info(
                            "  updating existing line qty to %s", qty_done)
                        continue

                    roll = wo.env['mrp.production.roll'].search([
                        ('name', '=', lot_name)
                    ], limit=1)
                    if not roll:
                        roll = wo.env['mrp.production.roll'].create({
                            'name': lot_name,
                            'total_qty': qty_done,
                        })

                    vals = {
                        'roll_id': roll.id,
                        'quantity': qty_done,
                        'prev_work_order_id': wo.id,
                    }
                    if ml.write_uid:
                        vals['user_id'] = ml.write_uid.id

                    _logger.info("  creating prev_roll_line roll=%s qty=%s",
                        roll.name, qty_done)
                    wo.env['mrp.wo.roll.line'].create(vals)

        for wo in self:
            _process_one_wo(wo)

        if len(self) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Work Order'),
                'view_mode': 'form',
                'res_model': 'mrp.workorder',
                'target': 'new',
                'res_id': self.id,
            }
        else:
            return {'type': 'ir.actions.client', 'tag': 'reload'}
    # def get_previous_rolls(self):
    #     """Batch-safe: populate prev_roll_line_ids from DONE pickings'
    #     lots for each WO."""
    #     precision = (
    #         self.env['decimal.precision'].precision_get(
    #             'Product Unit of Measure') or 2
    #     )

    #     def _process_one_wo(wo):
    #         allow_components = set()
    #         if wo.operation_id:
    #             for mv in wo.production_id.move_raw_ids:
    #                 op = getattr(mv.bom_line_id, 'operation_id', False)
    #                 if op and op.id == wo.operation_id.id:
    #                     allow_components.add(mv.product_id.id)

    #         if not allow_components:
    #             allow_components = {
    #                 mv.product_id.id
    #                 for mv in wo.production_id.move_raw_ids
    #             }

    #         pickings = wo.production_id.picking_ids.filtered(
    #             lambda p: p.state == 'done')
    #         if not pickings:
    #             return

    #         for picking in pickings:
    #             lines = (picking.move_line_ids_without_package
    #                      or picking.move_line_ids)
    #             lines = lines.filtered(
    #                 lambda ml: ml.product_id
    #                 and ml.product_id.id in allow_components
    #             )

    #             for ml in lines:
    #                 lot_name = (
    #                     (ml.lot_id and ml.lot_id.name) or ml.lot_name)
    #                 if not lot_name:
    #                     continue

    #                 qty_done = ml.qty_done or 0.0
    #                 if float_compare(
    #                         qty_done, 0.0,
    #                         precision_digits=precision) <= 0:
    #                     continue

    #                 exists = wo.prev_roll_line_ids.filtered(
    #                     lambda l: l.roll_id
    #                     and l.roll_id.name == lot_name
    #                     and float_compare(
    #                         l.quantity or 0.0, qty_done,
    #                         precision_digits=precision) == 0
    #                 )
    #                 if exists:
    #                     continue

    #                 roll = wo.env['mrp.production.roll'].search([
    #                     ('name', '=', lot_name)
    #                 ], limit=1)
    #                 if not roll:
    #                     roll = wo.env['mrp.production.roll'].create({
    #                         'name': lot_name,
    #                         'total_qty': qty_done,
    #                     })

    #                 vals = {
    #                     'roll_id': roll.id,
    #                     'quantity': qty_done,
    #                     'prev_work_order_id': wo.id,
    #                 }
    #                 if ml.write_uid:
    #                     vals['user_id'] = ml.write_uid.id

    #                 wo.env['mrp.wo.roll.line'].create(vals)

    #     for wo in self:
    #         _process_one_wo(wo)

    #     if len(self) == 1:
    #         return {
    #             'type': 'ir.actions.act_window',
    #             'name': _('Work Order'),
    #             'view_mode': 'form',
    #             'res_model': 'mrp.workorder',
    #             'target': 'new',
    #             'res_id': self.id,
    #         }
    #     else:
    #         return {'type': 'ir.actions.client', 'tag': 'reload'}

    def get_previous_roll_ids(self):
        self.ensure_one()
        precision = (
            self.env['decimal.precision'].precision_get(
                'Product Unit of Measure') or 2
        )

        allow_components = set()
        if self.operation_id:
            for mv in self.production_id.move_raw_ids:
                op = getattr(mv.bom_line_id, 'operation_id', False)
                if op and op.id == self.operation_id.id:
                    allow_components.add(mv.product_id.id)

        if not allow_components:
            allow_components = {
                mv.product_id.id
                for mv in self.production_id.move_raw_ids
            }

        pickings = self.production_id.picking_ids.filtered(
            lambda p: p.state == 'done')
        if not pickings:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Work Order'),
                'view_mode': 'form',
                'res_model': 'mrp.workorder',
                'target': 'new',
                'res_id': self.id,
            }

        for picking in pickings:
            lines = (picking.move_line_ids_without_package
                     or picking.move_line_ids)
            lines = lines.filtered(
                lambda ml: ml.product_id
                and ml.product_id.id in allow_components
            )

            for ml in lines:
                lot_name = (
                    (ml.lot_id and ml.lot_id.name) or ml.lot_name)
                if not lot_name:
                    continue
                qty_done = ml.qty_done or 0.0
                # Deduct consumption at same-WC predecessor WO if applicable
                deducted = self._get_lot_consumed_at_prev_same_wc_wo(lot_name)
                if deducted:
                    qty_done = max(qty_done - deducted, 0.0)
                if float_compare(
                        qty_done, 0.0,
                        precision_digits=precision) <= 0:
                    continue

                exists = self.prev_roll_line_ids.filtered(
                    lambda l: l.roll_id
                    and l.roll_id.name == lot_name
                )
                if exists:
                    # Update qty in case deduction changed it
                    exists[0].quantity = qty_done
                    continue

                roll = self.env['mrp.production.roll'].search([
                    ('name', '=', lot_name)
                ], limit=1)
                if not roll:
                    roll = self.env['mrp.production.roll'].create({
                        'name': lot_name,
                        'total_qty': qty_done,
                    })

                vals = {
                    'roll_id': roll.id,
                    'quantity': qty_done,
                    'prev_work_order_id': self.id,
                }
                if ml.write_uid:
                    vals['user_id'] = ml.write_uid.id
                self.env['mrp.wo.roll.line'].create(vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Work Order'),
            'view_mode': 'form',
            'res_model': 'mrp.workorder',
            'target': 'new',
            'res_id': self.id,
        }

    def update_roll_ids(self):
        roll_line = []
        for prev_line_rec in self.prev_roll_line_ids:
            roll_line.append((0, 0, {
                'prev_roll_id': prev_line_rec.roll_id.id,
                'quantity': prev_line_rec.quantity,
                'user_id': prev_line_rec.user_id.id,
                'date': prev_line_rec.date,
            }))
        self.roll_line_ids = roll_line
        return {
            'type': 'ir.actions.act_window',
            'name': 'Work Order',
            'view_mode': 'form',
            'res_model': 'mrp.workorder',
            'target': 'new',
            'res_id': self.id,
        }


