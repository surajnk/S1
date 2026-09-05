from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math
import logging
import json

_logger = logging.getLogger(__name__)

class MachineStops(models.Model):
    _name = 'machine.stops'

    x_machine_st = fields.Float('Machine Stops')

class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    x_embosser = fields.Boolean('Embosser')
    x_machine_frame = fields.Many2one('mrp.frames','Frame')
    x_frame_wc_id = fields.Char('Frame ID')
    x_frame_wc_type = fields.Selection([
        ('single', 'SINGLE'),
        ('turret', 'TURRET'),
        ('plater', 'PLATER'),
        ], 'Frame Type')
    x_frame_wc_number = fields.Integer('Frame Number')
    x_cylinder_wc_slot = fields.Integer('Cylinder Slot')
    x_frame_wc_status = fields.Boolean('Active')
    x_bottom_wc_roll = fields.Selection([
        ('poly', 'POLY'),
        ('felt', 'FELT'),
        ], 'Bottom Roll')
    x_pattern_wc = fields.Many2one('product.embossing','Top Roll')
    x_pattern_wc_number = fields.Char('Pattern Number')
    x_frame_branch_id = fields.Many2one('res.branch', string='Branch')

class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    x_code = fields.Char('Code')
    x_yards_per_hour = fields.Float('Yards Per Hour')

    x_time_before_prod = fields.Float('Time before prod.', help="Time in minutes for the setup.")
    x_clean_up_time = fields.Float('Clean up time.', help="Time in minutes for the setup.")
    from_exist_workcenter = fields.Boolean('From Exist Workcenter')
    exist_workcenter_id = fields.Many2one('mrp.routing.workcenter', 'Select from Existing Operations')

    @api.onchange('exist_workcenter_id')
    def onchange_exist_workcenter_id(self):
        """
        onchange Exist Work center
        """
        if self.exist_workcenter_id:
            self.name = self.exist_workcenter_id.name
            self.workcenter_id = self.exist_workcenter_id.workcenter_id and self.exist_workcenter_id.workcenter_id.id,
            self.sequence = self.exist_workcenter_id.sequence
            self.worksheet_type = self.exist_workcenter_id.worksheet_type
            self.note = self.exist_workcenter_id.note
            self.time_mode = self.exist_workcenter_id.time_mode
            self.time_mode_batch = self.exist_workcenter_id.time_mode_batch
            self.time_cycle_manual = self.exist_workcenter_id.time_cycle_manual
            self.capacity = self.exist_workcenter_id.capacity
            self.time_start = self.exist_workcenter_id.time_start
            self.time_stop = self.time_stop
        else:
            self.name = ''
            self.workcenter_id = False
            self.sequence = 100
            self.worksheet_type = 'text'
            self.note = ''
            self.time_mode = 'manual'
            self.time_mode_batch = 10
            self.time_cycle_manual = 60


    def write(self, vals):
        """
        When 'exist_workcenter_id' is written (e.g., via mass_editing), copy fields
        from that source operation into the current record(s), unless those fields
        are explicitly provided in 'vals' (explicit caller overrides win).

        This mirrors your form @api.onchange UX on the server side.
        """
        if 'exist_workcenter_id' in vals:
            exist_id = vals.get('exist_workcenter_id') or False
            vals = dict(vals)  # avoid mutating original dict

            if exist_id:
                src = self.env['mrp.routing.workcenter'].browse(exist_id)
                if src.exists():
                    # Add/remove fields here to match what you want mirrored
                    fields_to_copy = {
                        'name': src.name,
                        'workcenter_id': src.workcenter_id.id if src.workcenter_id else False,
                        'sequence': src.sequence,
                        'worksheet_type': src.worksheet_type,
                        'note': src.note,
                        'time_mode': src.time_mode,
                        'time_mode_batch': src.time_mode_batch,
                        'time_cycle_manual': src.time_cycle_manual,
                        'capacity': src.capacity,
                        'time_start': src.time_start,
                        'time_stop': src.time_stop,
                        # custom fields
                        'x_code': getattr(src, 'x_code', False),
                        'x_yards_per_hour': getattr(src, 'x_yards_per_hour', 0.0),
                        'x_time_before_prod': getattr(src, 'x_time_before_prod', 0.0),
                        'x_clean_up_time': getattr(src, 'x_clean_up_time', 0.0),
                        'from_exist_workcenter': True,
                    }
                    # Respect explicit overrides passed in vals
                    for field_name, value in fields_to_copy.items():
                        if field_name not in vals:
                            vals[field_name] = value
            else:
                # exist_workcenter_id cleared: only clear 'name' if caller didn't set it
                if 'name' not in vals:
                    vals['name'] = False
                if 'from_exist_workcenter' not in vals:
                    vals['from_exist_workcenter'] = False

        return super().write(vals)




class MrpFrames(models.Model):
    _name = 'mrp.frames'
    _rec_name = 'x_frame_id'

    x_frame_id = fields.Char('Frame ID')
    x_frame_type = fields.Selection([
        ('single', 'SINGLE'),
        ('turret', 'TURRET'),
        ('plater', 'PLATER'),
        ], 'Frame Type')
    x_frame_number = fields.Integer('Frame Number')
    x_cylinder_slot = fields.Integer('Cylinder Slot')
    x_frame_status = fields.Boolean('Active')
    x_bottom_roll = fields.Selection([
        ('poly', 'POLY'),
        ('felt', 'FELT'),
        ], 'Bottom Roll')
    x_pattern_number = fields.Many2one('product.embossing',string='Embossing Pattern')
    x_frame_branch_id = fields.Many2one('res.branch', string='NB')
    x_current_workorder = fields.Char(string='Current Workorder')
    x_wo_date = fields.Datetime('Date')
    

class MrpWorkCenterProductivity(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    x_yards_in = fields.Integer('Yards In')
    x_yards_out = fields.Integer('Yards Out')
    x_shift_time = fields.Many2one('shift.details',string='Shift')

    @api.depends('date_end', 'date_start')
    def _compute_duration(self):
        for blocktime in self:
            if blocktime.date_end:
                d1 = fields.Datetime.from_string(blocktime.date_start)
                d2 = fields.Datetime.from_string(blocktime.date_end)
                diff = d2 - d1
                if (blocktime.loss_type not in ('productive', 'performance')) and blocktime.workcenter_id.resource_calendar_id:
                    r = blocktime.workcenter_id._get_work_days_data_batch(d1, d2)[blocktime.workcenter_id.id]['hours']
                    blocktime.duration = round(r * 60, 2)
                else:
                    blocktime.duration = round(diff.total_seconds() / 60.0, 2)
            else:
                blocktime.duration = 0.0


    def write(self, vals):
        res = super(MrpWorkCenterProductivity, self).write(vals)

        # Only post when blocktime boundaries/length changed
        time_fields_touched = any(k in vals for k in ('date_start', 'date_end', 'duration'))
        if not time_fields_touched:
            return res

        for blocktime in self:
            # Guard: needs a WO, MO and a manufacturing journal
            if not (blocktime.workorder_id and blocktime.workorder_id.production_id
                    and blocktime.workorder_id.production_id.company_id.manufacturing_journal_id):
                continue

            _logger.info("Blocktime Workorder ID: %s", blocktime.workorder_id.id)
            _logger.info("Blocktime Production ID: %s", blocktime.workorder_id.production_id.id)
            _logger.info("Blocktime Company Manufacturing Journal ID: %s",
                         blocktime.workorder_id.production_id.company_id.manufacturing_journal_id.id)

            # Always upsert into the same move for this blocktime:
            blocktime.workorder_id._update_direct_lab_ovh_cost_postings(blocktime.id)

        return res


    # def write(self, vals):
    #     res = super(MrpWorkCenterProductivity, self).write(vals)

    #     for blocktime in self:
    #         # Run logic only if record has workorder and duration > 0
    #         if (
    #             blocktime.date_start
    #             and blocktime.date_end
    #             and blocktime.duration > 0
    #             and blocktime.workorder_id
    #             and blocktime.workorder_id.production_id
    #             and blocktime.workorder_id.production_id.company_id.manufacturing_journal_id
    #         ):
    #             _logger.info("Blocktime Workorder ID: %s", blocktime.workorder_id.id)
    #             _logger.info("Blocktime Production ID: %s", blocktime.workorder_id.production_id.id)
    #             _logger.info(
    #                 "Blocktime Company Manufacturing Journal ID: %s",
    #                 blocktime.workorder_id.production_id.company_id.manufacturing_journal_id.id
    #             )

    #             existing_lines = self.env['account.move'].search([('time_id', '=', blocktime.id)])
    #             if existing_lines:
    #                 blocktime.workorder_id._update_direct_lab_ovh_cost_postings(blocktime.id)
    #             else:
    #                 blocktime.workorder_id._direct_lab_ovh_cost_postings()

    #     return res

    # @api.model
    # def create(self, vals):
    #     # Perform additional operations if needed before creating the record
    #     _logger.info("HERREEEE INSIDE TIMESSS")
    #     record = super(MrpWorkCenterProductivity, self).create(vals)
    #     record.workorder_id._direct_lab_ovh_cost_postings()
    #     return record

class ShiftDetails(models.Model):
    _name = 'shift.details'
    _rec_name = 'x_shift_name'
    
    x_shift_name = fields.Char(string='Shift Name')
    x_shift_branch = fields.Many2one('res.branch',string='Branch')
    x_start_time = fields.Float(string='Start Time')
    x_end_time = fields.Float(string='End Time')

class ResourceCalendarAttendance(models.Model):
    _inherit = "resource.calendar.attendance"

    x_shift = fields.Many2one('shift.details',string='Shift')
    x_capacity = fields.Float(          # ADD THIS
        string='Capacity (Parallel Jobs)',
        default=0.0,
        help="Override parallel job slots for this shift slot. "
             "0 = use workcenter default capacity."
    )

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    workcenter_capacities = fields.Many2many(
        comodel_name='mrp.routing.workcenter',
        relation='mrp_bom_line_workcenter_rel',
        column1='bom_line_id',
        column2='workcenter_capacity_id',
        string='Multiple Operations',
        domain="[('id', 'in', allowed_operation_ids)]"
    )


class StockMove(models.Model):
    _inherit = 'stock.move'

    reserved_status = fields.Selection(
        selection=[
            ('available', 'Available'),
            ('none', 'Not Available'),
        ],
        string='Reserved Status',
        compute='_compute_reserved_status',
        store=True
    )

    @api.depends('product_uom_qty', 'forecast_availability')
    def _compute_reserved_status(self):
        for move in self:
            if move.forecast_availability >= move.product_uom_qty:
                move.reserved_status = 'available'
            else:
                move.reserved_status = 'none'



