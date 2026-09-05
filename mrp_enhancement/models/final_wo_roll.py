# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import models, fields, api, _
import logging
import math

_logger = logging.getLogger(__name__)

class MrpWOFinalRoll(models.Model):
    _name = 'final.wo.roll'

    workorder_id = fields.Many2one('mrp.workorder', string="Workorder") #M2o
    previous_roll_id = fields.Many2one('mrp.wo.roll.line', string='Input Roll', copy=0)
    user_id = fields.Many2one('res.users', string='Users')
    previous_roll_quantity = fields.Float(string="Quantity")
    date_start = fields.Datetime(string='Date', required=True, tracking=True, default=fields.Datetime.now)
    total_qty = fields.Float(string="Customer Qty", required=1)
    yards_qty = fields.Float(string="Qty(Yards)", compute="_compute_yards_qty",store=True)
    is_fully_consumed = fields.Boolean(string='Fully Consumed', copy=0)
    consumed_qty = fields.Float(string="Consumed Qty", copy=0)
    remained_qty = fields.Float(string="Remained Qty", compute="_compute_remained_qty", copy=0, readonly=0)
    partial_done_qty = fields.Float(string="Partially Done Quantity")


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
                    #_logger.info("CUSTOMERR LENGTH '%s'",customer_length)
                    if customer_width == component_width:
                        trim_width = 0
                                            #_logger.info("WITHHINNN NEW CONDITION22")
                        Width_Outs = (int(component_width - trim_width) / customer_width) or 1
                        _logger.info("WIDTHHH OUTS'%s'",Width_Outs)
                        Width_Outs_split_Dec,Width_Outs_split_Frac = math.modf(Width_Outs)
                        Width_Outs_final = math.trunc(Width_Outs_split_Frac)
                        _logger.info("WIDTHHH OUTS FINALLLLL'%s'",Width_Outs_final)
                        Master_Yards = int(customer_qty) / Width_Outs_final
                        _logger.info("MASTTTERRR YARDDSSSS'%s'",Master_Yards)
                        if not Master_Yards.is_integer():
                            Master_Yards = int(Master_Yards) + 1
                        rec.yards_qty = Master_Yards
                    #_logger.info("CUSTOMERR WIDTHHH '%s'",customer_width)
                    #_logger.info("COMPONNENNTTT WIDTHHH '%s'",component_width)
                    #_logger.info("\n\ncustomer_width '%s'",customer_width)
                    if customer_width != component_width and customer_length == '0.0':
                        #_logger.info("WITHHINNN NEW CONDITION22")
                        Width_Outs = int((component_width - trim_width) / customer_width) or 1
                        _logger.info("COMPONNNENNTTT WIDTHHH'%s'",component_width)
                        _logger.info("TRIMMMM WIDTHHH'%s'",trim_width)
                        _logger.info("CUSTOMMEERRR WIDTHHHHH'%s'",customer_width)
                        _logger.info("WIDTHHH OUTS'%s'",Width_Outs)
                        Width_Outs_split_Dec,Width_Outs_split_Frac = math.modf(Width_Outs)
                        Width_Outs_final = math.trunc(Width_Outs_split_Frac)
                        _logger.info("WIDTHHH OUTS FINALLLLL'%s'",Width_Outs_final)
                        Master_Yards = int(customer_qty) / Width_Outs_final
                        _logger.info("MASTTTERRR YARDDSSSS'%s'",Master_Yards)
                        if not Master_Yards.is_integer():
                            Master_Yards = int(Master_Yards) + 1
                        rec.yards_qty = Master_Yards
                    if customer_length != '0.0':
                        _logger.info("=== yards_qty computation START for record %s ===", rec.id)

                        # 1. Log all key inputs upfront
                        _logger.info(
                            "INPUTS => component_width=%s | trim_width=%s | customer_width=%s | "
                            "customer_length=%s | trim_length=%s | machine_length=%s | customer_qty=%s",
                            component_width,
                            trim_width,
                            customer_width,
                            customer_length,
                            trim_length,
                            machine_length,
                            customer_qty,
                        )

                        # 2. How many times customer_width fits into the component width (after trim)
                        Width_Outs = int((component_width - trim_width) / customer_width)
                        _logger.info(
                            "Width_Outs (raw count of pieces across width) = int((%s - %s) / %s) = %s",
                            component_width,
                            trim_width,
                            customer_width,
                            Width_Outs,
                        )

                        Width_Outs_split_Dec, Width_Outs_split_Frac = math.modf(Width_Outs)
                        _logger.info(
                            "Width_Outs split => decimal_part=%s | fractional_part=%s",
                            Width_Outs_split_Dec,
                            Width_Outs_split_Frac,
                        )

                        Width_Outs_final = math.trunc(Width_Outs_split_Frac)
                        _logger.info("Width_Outs_final (usable pieces across width) = %s", Width_Outs_final)

                        # 3. Start with 1 piece in length direction and see how many fit into machine length
                        counter = 1
                        Length_Outs = (counter * customer_length) + trim_length
                        _logger.info(
                            "Initial Length_Outs with counter=%s => (counter * customer_length) + trim_length "
                            "= (%s * %s) + %s = %s",
                            counter,
                            counter,
                            customer_length,
                            trim_length,
                            Length_Outs,
                        )

                        Length_Outs_split_Dec, Length_Outs_split_Frac = math.modf(Length_Outs)
                        Length_Outs_final = math.trunc(Length_Outs_split_Frac)
                        _logger.info(
                            "Length_Outs split => decimal_part=%s | fractional_part=%s | "
                            "Length_Outs_final (as int)=%s",
                            Length_Outs_split_Dec,
                            Length_Outs_split_Frac,
                            Length_Outs_final,
                        )

                        _logger.info("Machine_length (maximum usable length) = %s", machine_length)

                        # 4. Increase counter until we exceed machine_length, then step back by one
                        while Length_Outs_final < machine_length:
                            _logger.info(
                                "While loop => current counter=%s | current Length_Outs_final=%s "
                                "(< machine_length=%s) => increment counter",
                                counter,
                                Length_Outs_final,
                                machine_length,
                            )
                            counter += 1
                            Length_Outs_final = (counter * customer_length) + trim_length
                            _logger.info(
                                "Updated Length_Outs_final with new counter=%s => (%s * %s) + %s = %s",
                                counter,
                                counter,
                                customer_length,
                                trim_length,
                                Length_Outs_final,
                            )

                        # At this point, counter made Length_Outs_final >= machine_length; we step back by 1
                        Length_Outs_final = counter - 1
                        _logger.info(
                            "After while loop => final counter allowed=%s | Length_Outs_final (count of pieces in length direction) = %s",
                            counter,
                            Length_Outs_final,
                        )

                        # 5. Compute theoretical master sheet length from that count
                        Master_Sheet_Length = (Length_Outs_final * customer_length) + trim_length
                        _logger.info(
                            "Master_Sheet_Length before machine.stops adjustment => "
                            "(Length_Outs_final * customer_length) + trim_length = "
                            "(%s * %s) + %s = %s",
                            Length_Outs_final,
                            customer_length,
                            trim_length,
                            Master_Sheet_Length,
                        )

                        # 6. Snap Master_Sheet_Length to the next available machine stop length
                        machine_stops_ids = self.env['machine.stops'].search(
                            [('x_machine_st', '>=', Master_Sheet_Length)],
                            limit=1
                        )
                        _logger.info(
                            "machine.stops search domain => x_machine_st >= %s | found record=%s",
                            Master_Sheet_Length,
                            machine_stops_ids,
                        )

                        if machine_stops_ids:
                            Master_Sheet_Length = machine_stops_ids.x_machine_st
                            _logger.info(
                                "Master_Sheet_Length adjusted to machine stop => %s",
                                Master_Sheet_Length,
                            )
                        else:
                            _logger.info(
                                "No machine.stops found with x_machine_st >= %s, keeping Master_Sheet_Length=%s",
                                Master_Sheet_Length,
                                Master_Sheet_Length,
                            )

                        _logger.info("FINAL Master_Sheet_Length used => %s", Master_Sheet_Length)

                        # 7. Calculate Master_Outs (total pieces per master sheet)
                        Master_Outs = (Width_Outs_final * Length_Outs_final) or 1
                        _logger.info(
                            "Master_Outs (pieces per master sheet) => Width_Outs_final * Length_Outs_final "
                            "= %s * %s = %s",
                            Width_Outs_final,
                            Length_Outs_final,
                            Master_Outs,
                        )

                        # 8. How many master sheets are needed for the customer quantity
                        Master_Sheets = (int(customer_qty) / Master_Outs)
                        _logger.info(
                            "Master_Sheets (raw) => int(customer_qty) / Master_Outs = %s / %s = %s",
                            int(customer_qty),
                            Master_Outs,
                            Master_Sheets,
                        )

                        if not Master_Sheets.is_integer():
                            _logger.info(
                                "Master_Sheets is not integer (%s), rounding up to next full sheet",
                                Master_Sheets,
                            )
                            Master_Sheets = int(Master_Sheets) + 1
                        else:
                            _logger.info(
                                "Master_Sheets is already an integer (%s), no need to round up",
                                Master_Sheets,
                            )

                        _logger.info("Master_Sheets (final, rounded) = %s", Master_Sheets)

                        # 9. Convert total master sheet length into yards
                        Master_Yards = int(Master_Sheets * Master_Sheet_Length) / 36
                        _logger.info(
                            "Master_Yards (raw) => int(Master_Sheets * Master_Sheet_Length) / 36 "
                            "= int(%s * %s) / 36 = %s",
                            Master_Sheets,
                            Master_Sheet_Length,
                            Master_Yards,
                        )

                        if not Master_Yards.is_integer():
                            _logger.info(
                                "Master_Yards is not integer (%s), rounding up to next full yard",
                                Master_Yards,
                            )
                            Master_Yards = int(Master_Yards) + 1
                        else:
                            _logger.info(
                                "Master_Yards is already integer (%s), no need to round up",
                                Master_Yards,
                            )

                        _logger.info("Master_Yards (final, rounded) = %s", Master_Yards)

                        # 10. Write result to record
                        rec.yards_qty = Master_Yards
                        _logger.info(
                            "yards_qty set on record %s => %s",
                            rec.id,
                            rec.yards_qty,
                        )
                        _logger.info("=== yards_qty computation END for record %s ===", rec.id)

            else:
                rec.yards_qty = 0

    @api.depends('total_qty', 'consumed_qty')
    def _compute_remained_qty(self):
        for rec in self:
            rec.remained_qty = rec.previous_roll_quantity - rec.consumed_qty
            rec.previous_roll_id.remained_qty = rec.previous_roll_quantity - rec.consumed_qty

    @api.onchange('is_fully_consumed')
    def onchange_is_fully_consumed(self):
        if self.is_fully_consumed:
            self.previous_roll_id.status = 'done'
        else:
            self.previous_roll_id.status = 'available'

    @api.onchange('previous_roll_id')
    def _onchange_previous_roll_id_quantity(self):
        if self.previous_roll_id:
            self.previous_roll_quantity = self.previous_roll_id.quantity

    @api.model_create_multi
    def create(self, vals_list):
        return super(MrpWOFinalRoll, self).create(vals_list)

