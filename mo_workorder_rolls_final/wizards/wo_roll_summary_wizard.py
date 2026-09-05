from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class WoRollSummaryWizard(models.TransientModel):
    _name = 'wo.roll.summary.wizard'
    _description = 'Workorder Rolls Summary Wizard'

    lot_id = fields.Many2one('stock.production.lot', string='Lot Number')
    production_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
    )
    workorder_line_ids = fields.One2many(
        'wo.roll.summary.line',
        'wizard_id',
        string='Workorders',
        readonly=True,
    )

    def print_report(self):
        return self.env.ref(
            'mo_workorder_rolls_final.action_report_wo_roll_summary_line'
        ).report_action(self)

    def action_search(self):
        # 1. If user only selected lot, figure out the MO from that lot
        if self.lot_id and not self.production_id:
            lot = self.lot_id

            Production = self.env['mrp.production']
            MoveLine = self.env['stock.move.line']
            StockMove = self.env['stock.move']

            mo = False

            # STEP A:
            # Find a stock.move.line for THIS lot, where its parent stock.move
            # is a finished product move (i.e. move.production_id is set).
            #
            # This corresponds to the MO that actually CREATED this lot.
            move_line = MoveLine.search([
                ('lot_id', '=', lot.id),
                ('move_id.production_id', '!=', False),
            ], order='id asc', limit=1)

            if move_line:
                mo = move_line.move_id.production_id
                _logger.info("MO via move_id.production_id: %s", mo.name)

            # STEP B (fallback):
            # If not found, sometimes data ends up hanging off workorders or
            # post-production transfer steps. We'll still try other links,
            # but only if STEP A failed.
            if not mo:
                # workorder -> production
                move_line_wo = MoveLine.search([
                    ('lot_id', '=', lot.id),
                    ('workorder_id.production_id', '!=', False),
                ], order='id asc', limit=1)
                if move_line_wo:
                    mo = move_line_wo.workorder_id.production_id
                    _logger.info("MO via workorder.production_id: %s", mo.name)

            if not mo:
                # rare: lot recorded on mrp.production.lot_producing_id
                mo = Production.search([
                    ('lot_producing_id', '=', lot.id),
                ], limit=1)
                if mo:
                    _logger.info("MO via lot_producing_id: %s", mo.name)

            # If still nothing, last resort (not expected in your screenshot case)
            if not mo:
                raise UserError(
                    _('No manufacturing order found for selected lot.')
                )

            # assign
            self.production_id = mo

        # 2. If we *still* don't have production_id, user didn't fill either field
        if not self.production_id:
            raise UserError(_('Please select a manufacturing order or lot.'))

        # 3. Build the workorder lines for the wizard (unchanged from your logic)
        self.workorder_line_ids.unlink()
        lines = []
        Lot = self.env['stock.production.lot']
        for wo in self.production_id.workorder_ids:
            roll_lines = []
            final_roll_lines = []

            for rl in wo.roll_line_ids:
                product_id_val = False

                # We try to map prev_roll_id -> stock.production.lot by name
                if rl.prev_roll_id and rl.prev_roll_id.name:
                    lot_rec = Lot.search([
                        ('name', '=', rl.prev_roll_id.name)
                    ], limit=1)

                    if lot_rec:
                        # lot_rec.product_id is Many2one('product.product')
                        product_id_val = lot_rec.product_id.id

                roll_lines.append((0, 0, {
                    'roll_id': rl.roll_id.id,
                    'prev_roll_id': rl.prev_roll_id.id,
                    'product_id': product_id_val, 
                    'consumed_qty': rl.consumed_qty,
                    'remained_qty': rl.prev_roll_remained_qty,
                    'date': rl.date,
                    'user_id': rl.user_id.id,
                }))

            for fr in wo.final_roll_line_ids:
                final_roll_lines.append((0, 0, {
                    'previous_roll_id': fr.previous_roll_id.id,
                    'user_id': fr.user_id.id,
                    'remained_qty': fr.remained_qty,
                    'is_fully_consumed': fr.is_fully_consumed,
                    'consumed_qty': fr.consumed_qty,
                    'total_qty': fr.total_qty,
                    'yards_qty': fr.yards_qty,
                    'date': fr.date_start,
                }))

            lines.append((0, 0, {
                'workorder_id': wo.id,
                'roll_line_ids': roll_lines,
                'final_roll_line_ids': final_roll_lines,
            }))

        self.workorder_line_ids = lines

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wo.roll.summary.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }



class WoRollSummaryLine(models.TransientModel):
    _name = 'wo.roll.summary.line'
    _description = 'Workorder Rolls Summary Line'

    wizard_id = fields.Many2one('wo.roll.summary.wizard')
    workorder_id = fields.Many2one('mrp.workorder', string='Workorder')
    roll_line_ids = fields.One2many(
        'wo.roll.summary.roll.line',
        'summary_line_id',
        string='Output Rolls',
        readonly=True,
    )
    final_roll_line_ids = fields.One2many(
        'wo.roll.summary.final.roll.line',
        'summary_line_id',
        string='Final Output Rolls',
        readonly=True,
    )



class WoRollSummaryRollLine(models.TransientModel):
    _name = 'wo.roll.summary.roll.line'
    _description = 'Workorder Roll Detail Line'

    summary_line_id = fields.Many2one('wo.roll.summary.line')
    roll_id = fields.Many2one('mrp.production.roll', string='Output Roll')
    prev_roll_id = fields.Many2one('mrp.production.roll', string='Input Roll')
    consumed_qty = fields.Float(string='Consumed Qty')
    remained_qty = fields.Float(string='Remaining Qty')
    user_id = fields.Many2one('res.users', string='User')
    date = fields.Datetime(string='Date')
    product_id = fields.Many2one(
    'product.product',
    string='Prev Roll Product',
    readonly=True,)


class WoRollSummaryFinalRollLine(models.TransientModel):
    _name = 'wo.roll.summary.final.roll.line'
    _description = 'Workorder Final Roll Detail Line'

    summary_line_id = fields.Many2one('wo.roll.summary.line')
    previous_roll_id = fields.Many2one('mrp.wo.roll.line', string='Input Roll')
    user_id = fields.Many2one('res.users', string='User')
    remained_qty = fields.Float(string='Remained Qty')
    is_fully_consumed = fields.Boolean(string='Fully Consumed')
    consumed_qty = fields.Float(string='Consumed Qty')
    total_qty = fields.Float(string='Customer Qty')
    yards_qty = fields.Float(string='Qty(Yards)')
    date = fields.Datetime(string='Date')
