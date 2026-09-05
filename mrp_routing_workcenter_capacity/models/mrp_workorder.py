# Copyright 2021 Alfredo de la fuente - AvanzOSC
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import models, fields, _, api
from odoo.exceptions import Warning
import logging
import datetime
import pytz

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    duration_expected_hrs = fields.Float(
        'Scheduled Hrs', digits=(16, 2),
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Expected duration (in Hours)")

    # @api.onchange('operation_id', 'workcenter_id', 'qty_production')
    # def _onchange_expected_duration_hrs(self):
    #     self.duration_expected_hrs = self._get_duration_expected_hrs()

    def get_op_capacity(self, operation, workcenter, product):
        """
        product > Commodity code == operation > paroduct details > commodity code
        if we get any line then have to take capacity (per yards) from that line and use in
        calculation for expected duration.
        if not any line then use operation or workcenter.
        """
        capacity = (operation.capacity if operation.capacity else workcenter.capacity)
        if product and product.x_class_commodity_group and operation and operation.routing_wc_product_line_ids:
            product_detail_lines = operation.routing_wc_product_line_ids.filtered(lambda r: r.commodity_categ_id and r.commodity_categ_id.id == product.x_class_commodity_group.id)
            if product_detail_lines:
                capacity = product_detail_lines[0].capacity
        return capacity

    def get_op_interval(self, operation, workcenter, qty_production):
        op_interval = 0.00
        for reca in operation.routing_operation_interval_ids:
            rl1=rl2=nameval_gap=''
            labor_charge=labor_extension=0
            nameval_gap = reca.qty_prod_gap.split("-")
            if ((qty_production >= int(nameval_gap[0])) and (qty_production <= int(nameval_gap[1]))): 
                op_interval = reca.qty_prod_gap_hrs
        return op_interval


    def _get_duration_expected_hrs(self, alternative_workcenter=False, ratio=1):
        self.ensure_one()

        _logger.info("========== _get_duration_expected_hrs START ==========")

        # Base information
        _logger.info("WO: %s | Product: %s", self.name, self.production_id.product_id.display_name)
        _logger.info("Workcenter: %s | Operation: %s",
                     self.workcenter_id.display_name, self.operation_id.display_name)

        if not self.workcenter_id and not self.operation_id:
            _logger.info("Missing workcenter or operation. Falling back to super()")
            return super(MrpWorkorder, self)._get_duration_expected(
                alternative_workcenter=alternative_workcenter, ratio=ratio)

        # Quantity conversion
        qty_source = self.qty_output_wo or self.qty_production
        qty_production = self.production_id.product_uom_id._compute_quantity(
            qty_source, self.production_id.product_id.uom_id
        )
        _logger.info("qty_source: %s | qty_production (converted): %s", qty_source, qty_production)

        # Capacity
        capacity = self.get_op_capacity(self.operation_id, self.workcenter_id, self.production_id.product_id)
        _logger.info("Operation Capacity: %s", capacity)

        # Interval (already in hours from get_op_interval) → convert to MINUTES
        interval_hrs = self.get_op_interval(self.operation_id, self.workcenter_id, qty_production)
        _logger.info("Interval Hours (returned): %s", interval_hrs)

        interval_hrs_final = interval_hrs or 0.00
        _logger.info("Interval Hours Final (before *60): %s", interval_hrs_final)

        if interval_hrs_final > 0.00:
            interval_hrs_final *= 60.0  # → minutes
        _logger.info("Interval Minutes Final: %s", interval_hrs_final)

        # Cycle calculation
        cycle_number = 0.0
        if capacity:
            cycle_number = qty_production / capacity
        _logger.info("Cycle Number: %s", cycle_number)

        # Get start/stop times – keep them in MINUTES
        if self.operation_id.time_start or self.operation_id.time_stop:
            time_start = self.operation_id.time_start      # minutes
            time_stop = self.operation_id.time_stop        # minutes
            source = "Operation"
        else:
            time_start = self.workcenter_id.time_start     # minutes
            time_stop = self.workcenter_id.time_stop       # minutes
            source = "Workcenter"

        _logger.info("Time Start (min): %s | Time Stop (min): %s | Source: %s",
                     time_start, time_stop, source)

        # Alternative workcenter branch – keep it consistent (minutes → hours)
        if alternative_workcenter:
            _logger.info("--- Alternative Workcenter Mode Enabled ---")
            if cycle_number:
                duration_expected_working = (
                    (self.duration_expected - time_start - time_stop)
                    * self.workcenter_id.time_efficiency
                    / (100.0 * cycle_number)
                )
            else:
                duration_expected_working = 0.0

            if duration_expected_working < 0:
                duration_expected_working = 0

            final_minutes = (
                alternative_workcenter.time_start +
                alternative_workcenter.time_stop +
                cycle_number * duration_expected_working * 100.0 / alternative_workcenter.time_efficiency
            )
            _logger.info("Alternative Calculation Final Value (minutes): %s", final_minutes)

            final_hours = final_minutes / 60.0
            dur_expected_final = float('%.2f' % final_hours)
            _logger.info("Alternative Duration (decimal hours): %s", dur_expected_final)
            _logger.info("========== _get_duration_expected_hrs END ==========")
            return dur_expected_final

        # Regular duration calculation (all in MINUTES)
        time_cycle = self.operation_id.time_cycle_manual or 60.0  # minutes
        time_efficiency = self.workcenter_id.time_efficiency or 1.0

        _logger.info("Time Cycle (manual, min): %s | Time Efficiency: %s",
                     time_cycle, time_efficiency)

        total_minutes = (
            interval_hrs_final
            + time_start
            + time_stop
            + cycle_number * time_cycle * 100.0 / time_efficiency
        )
        _logger.info("Total Duration (minutes): %s", total_minutes)

        # Convert to decimal hours → e.g. 3.29
        total_hours = total_minutes / 60.0
        dur_expected_final = float('%.2f' % total_hours)

        _logger.info("Final Duration (decimal hours): %s", dur_expected_final)
        _logger.info("========== _get_duration_expected_hrs END ==========")

        return dur_expected_final


    def _get_duration_expected(self, alternative_workcenter=False, ratio=1):
        self.ensure_one()
        interval_hrs_final = 0.00
        if not self.workcenter_id and not self.operation_id:
            return super(MrpWorkorder, self)._get_duration_expected(
                alternative_workcenter=alternative_workcenter, ratio=ratio)
        qty_source = self.qty_output_wo or self.qty_production
        qty_production = self.production_id.product_uom_id._compute_quantity(
            qty_source, self.production_id.product_id.uom_id)
        capacity = self.get_op_capacity(self.operation_id, self.workcenter_id, self.production_id.product_id)
        interval_hrs = self.get_op_interval(self.operation_id,self.workcenter_id,qty_production)
        if interval_hrs:
            interval_hrs_final = interval_hrs
        else:
            interval_hrs_final = 0.00
        if interval_hrs_final > 0.00:
            interval_hrs_final =  interval_hrs_final * 60
        cycle_number = 0
        if capacity:
            cycle_number = (qty_production / capacity)
                                   #precision_digits=0, rounding_method='UP')
        if self.operation_id.time_start or self.operation_id.time_stop:
            time_start = self.operation_id.time_start
            time_stop = self.operation_id.time_stop
        else:
            time_start = self.workcenter_id.time_start
            time_stop = self.workcenter_id.time_stop
        if alternative_workcenter:
            duration_expected_working = (
                (self.duration_expected - time_start - time_stop) *
                self.workcenter_id.time_efficiency / (100.0 * cycle_number))
            if duration_expected_working < 0:
                duration_expected_working = 0
            return (alternative_workcenter.time_start +
                    alternative_workcenter.time_stop +
                    cycle_number * duration_expected_working * 100.0 /
                    alternative_workcenter.time_efficiency)
        time_cycle = self.operation_id and self.operation_id.time_cycle_manual or 60.0
        time_efficiency = self.workcenter_id.time_efficiency or 1
        #_logger.info("DURATIONNNN '%s'",(time_start + time_stop + cycle_number * time_cycle * 100.0 / time_efficiency))
        self.duration_expected_hrs = self._get_duration_expected_hrs()
        return (interval_hrs_final + time_start + time_stop + cycle_number * time_cycle * 100.0 / time_efficiency)

    def write(self, vals):
        # First do the normal write (including all core validations)
        res = super(MrpWorkorder, self).write(vals)

        # If qty_output_wo changed, recompute duration fields
        if 'qty_output_wo' in vals:
            for wo in self:
                if not wo.workcenter_id or not wo.operation_id:
                    continue
                # Recompute using your patched helpers
                wo.duration_expected = wo._get_duration_expected()
                # wo.duration_expected_hrs = wo._get_duration_expected_hrs()

        return res


    def open_mrp_production_components(self):
        if self and self.production_id:
            view_id = self.env.ref('mrp_routing_workcenter_capacity.mrp_production_only_components_view').id
            return {
                'name': _("Product to Consume"),
                'view_mode': 'form',
                'view_id': view_id,
                'view_type': 'form',
                'res_model': 'mrp.production',
                'res_id': self.production_id.id,
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': '[]',
                'context': {}
            }
        else:
            raise Warning(_('Work Order is not Links with the Production.'))

    def open_workcenter_productivity(self):
        """
        """
        if self:
            view_id = self.env.ref('mrp_shop_floor_control.mrp_wo_roll_line_tree_view').id
            return {
                'name': _("Productivity(Roll) Label"),
                'view_mode': 'tree',
                'view_id': view_id,
                'res_model': 'mrp.wo.roll.line',
                'type': 'ir.actions.act_window',
                'nodestroy': True,
                'target': 'new',
                'domain': [('id', 'in', self.roll_line_ids.ids)],
                'context': {
                    # 'default_workcenter_id': self.workcenter_id.id,
                    'default_workorder_id': self.id
                }
            }

    @api.model
    def get_productivity_label_data(self, roll_line, work_order):
        """
        Get Productivity
        """
        data_lines = []
        total_yards = 0
        production_rec = work_order.production_id
        sale_order = self.env['sale.order']
        sale_order_ids = work_order.production_id.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id.ids
        if sale_order_ids:
            sale_order = self.env['sale.order'].browse(sale_order_ids[0])
        sale_order_line = self.env['sale.order.line']
        if sale_order:
            sale_order_line = sale_order.order_line.filtered(lambda x: x.product_id.id == production_rec.product_id.id)
        #for wo in production_rec.workorder_ids:
        line_data = {
        'machine': work_order.workcenter_id.name,
        'lines': []
        }
        lines = []
        for r_line in work_order.roll_line_ids.filtered(lambda x: x.id == roll_line.id):
            lines.append({
                'operator': r_line.user_id and r_line.user_id.name,
                # 'date': datetime.datetime.strptime(str(r_line.date), '%Y-%m-%d %H:%M:%S.%f').strftime('%m-%d-%Y %H:%M'),
                'date': r_line.date.strftime('%m-%d-%Y %H:%M') if r_line.date else '',
                'roll_name': r_line.roll_id.name,
                'yards': r_line.quantity,
                'location': ''
            })
            total_yards += r_line.quantity
        line_data['lines'] = lines
        data_lines.append(line_data)
            # line_data = {
            #     'machine': wo.workcenter_id.name,
            #     'lines': []
            # }
            # lines = []
            # # if wo.id == work_order.id:
            # for r_line in wo.roll_line_ids:
            #         # if r_line.id == roll_line.id:
            #     lines.append({
            #         # 'operator': time.user_id and time.user_id.name,
            #         # 'end_date': time.date_end,
            #         'operator': r_line.user_id and r_line.user_id.name,
            #         'date': datetime.datetime.strptime(str(r_line.date), '%Y-%m-%d %H:%M:%S.%f').strftime('%m-%d-%Y %H:%M'),
            #         'roll_name': r_line.roll_id.name,
            #         'yards': r_line.quantity,
            #         'location': ''
            #     })
            #     if wo.id == work_order.id:
            #         if r_line.id == roll_line.id:
            #             total_yards += r_line.quantity
            # line_data['lines'] = lines
            # data_lines.append(line_data)
        return {
            'sale_name': sale_order and sale_order.name,
            'data_lines': data_lines,
            'total_yards': total_yards and int(total_yards) or 0,
            'item': production_rec.product_id.name or '',
            'efi_po': sale_order and sale_order.client_order_ref or '',
            'name_01': production_rec.product_id.default_code,
            'name_02': production_rec.product_id.x_product_product_embossing and
                       production_rec.product_id.x_product_product_embossing.name or '',
            'customer_width': sale_order_line and sale_order_line.x_customer_order_width or 0,
            'customer_ref': sale_order and sale_order.partner_id and sale_order.partner_id.ref or '',
            'so_expected_date': sale_order and sale_order.commitment_date and sale_order.commitment_date.date() or
                                sale_order and sale_order.expected_date and sale_order.expected_date.date() or ''
        }


class MrpWoRollLine(models.Model):
    _inherit="mrp.wo.roll.line"


    def print_roll_label(self):
        return {
            'type': 'ir.actions.act_url',
            'url': f'/mrp/roll_label_zpl/{self.id}',
            'target': 'new',  # opens in new tab → triggers download
        }
    # def print_roll_label(self):
    #     """
    #     """
    #     return self.env.ref('mrp_routing_workcenter_capacity.mrp_workcenter_productivity_label').report_action(self)