# -*- coding: utf-8 -*-


from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    def compute_expected_delivery_date(self):
        """
        """
        for rec in self:
            date = False
            if rec.production_id and rec.production_id.origin:
                so_rec = self.env['sale.order'].search([('name', '=', rec.production_id.origin)])
                if so_rec and so_rec.commitment_date:
                    date = so_rec.commitment_date
            rec.expected_delivery_date = date

    prev_date_planned_start_wo = fields.Datetime(string='Previous Scheduled Start Date ', readonly=True)
    expected_delivery_date = fields.Datetime(string='Expected Delivery Date', compute="compute_expected_delivery_date")
    top_roll = fields.Char(string='Top Roll')
    x_pattern_wo = fields.Many2one(
            'product.embossing', 'Pattern', store=True, readonly=False)

    def write(self, values):
        if values.get('date_planned_start_wo', False):
            self.prev_date_planned_start_wo = self.date_planned_start_wo
        return super().write(values)

    def mid_point_scheduling_engine(self):
        for workorder in self:
            sequence_wo = workorder.operation_id.sequence
            max_date_finished = False
            min_date_start = False
            max_date_finished_in_progress = False

            parall_workorders = self.search([
                ('production_id', '=', workorder.production_id.id),
                ('state', 'in', ('ready','pending','progress'))]).filtered(lambda r: r.sequence == sequence_wo)
            if parall_workorders:
                wos_in_progress = parall_workorders.filtered(lambda r: r.state == 'progress').sorted(key=lambda r: r.date_planned_finished_wo)
                if wos_in_progress:
                    last_wo_in_progress = wos_in_progress[-1]
                    max_date_finished_in_progress = last_wo_in_progress.date_planned_finished_wo
                current_workorder = workorder
                for parall_workorder in parall_workorders:
                    if not parall_workorder.state == 'progress':
                        parall_workorder.date_planned_start_wo = current_workorder.date_planned_start_wo
                        parall_workorder.forwards_scheduling()
                        if max_date_finished_in_progress and parall_workorder.date_planned_finished_wo < max_date_finished_in_progress:
                            raise UserError(_('backward scheduling is not possible'))
                    max_date_finished = max(parall_workorder.date_planned_finished_wo, current_workorder.date_planned_finished_wo)
                    min_date_start = min(parall_workorder.date_planned_start_wo, current_workorder.date_planned_start_wo)

            prev_workorders = self.search([
                ('production_id', '=', workorder.production_id.id),
                ('state', 'in', ('ready','pending','progress'))]).filtered(lambda r: r.sequence < sequence_wo).sorted(key=lambda r: r.sequence, reverse=True)
            if prev_workorders:
                current_workorder = workorder
                for prev_workorder in prev_workorders:
                    if prev_workorder.state == 'progress':
                        if prev_workorder.date_planned_finished_wo > current_workorder.date_planned_start_wo:
                            raise UserError(_('backward scheduling is not possible'))
                        else:
                            break
                    else:
                        if not current_workorder.sequence == prev_workorder.sequence:
                            prev_workorder.date_planned_finished_wo = min_date_start or current_workorder.date_planned_start_wo
                        else:
                            prev_workorder.date_planned_finished_wo = current_workorder.date_planned_finished_wo
                        prev_workorder.backwards_scheduling()
                        if current_workorder.date_planned_start_wo and prev_workorder.date_planned_start_wo:
                            min_date_start = min(prev_workorder.date_planned_start_wo, current_workorder.date_planned_start_wo)
                        else:
                            min_date_start = prev_workorder.date_planned_start_wo
                        current_workorder = prev_workorder

            succ_workorders = self.search([
                ('production_id', '=', workorder.production_id.id),
                ('state', 'in', ('ready','pending','progress'))]).filtered(lambda r: r.sequence > sequence_wo).sorted(key=lambda r: r.sequence)
            if succ_workorders:
                current_workorder = workorder
                for succ_workorder in succ_workorders:
                    if succ_workorder.state == 'progress':
                        if succ_workorder.date_planned_start_wo < current_workorder.date_planned_finished_wo:
                            raise UserError(_('forward scheduling is not possible'))
                        else:
                            break
                    else:
                        if not current_workorder.sequence == succ_workorder.sequence:
                            succ_workorder.date_planned_start_wo = max_date_finished or current_workorder.date_planned_finished_wo
                        else:
                            succ_workorder.date_planned_start_wo = current_workorder.date_planned_start_wo
                        succ_workorder.forwards_scheduling()
                        if succ_workorder.date_planned_finished_wo and current_workorder.date_planned_finished_wo:
                            max_date_finished = max(succ_workorder.date_planned_finished_wo, current_workorder.date_planned_finished_wo)
                        else:
                            max_date_finished = succ_workorder.date_planned_finished_wo
                        current_workorder = succ_workorder
            workorder.production_id.date_planned_start_wo = min_date_start
            workorder.production_id.date_planned_finished_wo = max_date_finished
        return True


class set_date_wizard(models.TransientModel):
    _name = 'set.date.wizard'
    _description = "Mid Point Scheduling Wizard"

    new_date_planned_start_wo = fields.Datetime(string=_('New Scheduled Start Date'), required=True)
    workorder_id = fields.Many2one('mrp.workorder', string="Workorder", readonly=True)

    @api.model
    def default_get(self, fields):
        default = super().default_get(fields)
        active_id = self.env.context.get('active_id', False)
        if active_id:
            default['workorder_id'] = active_id
        return default

    def set_date(self):
        workorder_id = self.env.context.get('active_id', False)
        if workorder_id:
            workorder = self.env['mrp.workorder'].browse(workorder_id)
            if workorder.state == 'progress':
                raise UserError(_('midpoint scheduling cannot be performed for workorder in progress'))
            # if not workorder.date_planned_start_wo:
            #     raise UserError(_('Manufacturing Order not scheduled yet'))
            workorder.write({'date_planned_start_wo': self.new_date_planned_start_wo})
            workorder.mid_point_scheduling_engine()
        return True

    # def get_privious_work_order(self, workorder_rec):

    def _do_reverse_lst(self, lst):
        return [ele for ele in reversed(lst)]

    def set_date_with_previous_work_order(self):
        """
        Set Work Order Date with Previous Date
        """
        workorder_id = self.env.context.get('active_id', False)
        if workorder_id:
            workorder = self.env['mrp.workorder'].browse(workorder_id)
            work_order_list = []
            for wo_line in workorder.production_id.workorder_ids:
                if wo_line.id == workorder.id:
                    work_order_list.append(wo_line)
                    break
                work_order_list.append(wo_line)
            count = 0
            new_date_planned_start_wo = self.new_date_planned_start_wo
            for wo_line_rec in self._do_reverse_lst(work_order_list):
                if wo_line_rec.state == 'progress':
                    raise UserError(_('Midpoint Scheduling cannot be performed for workorder which is in progress.'))
                # if not wo_line_rec.date_planned_start_wo:
                #     raise UserError(_('Manufacturing Order not scheduled yet'))
                if count == 0:
                    duration_expected = wo_line_rec.duration_expected
                    end_date = new_date_planned_start_wo + timedelta(minutes=duration_expected)
                    wo_line_rec.write({
                        'date_planned_start_wo': new_date_planned_start_wo,
                        'date_planned_finished_wo': end_date})
                    count = 1
                else:
                    end_date = new_date_planned_start_wo
                    duration_expected = wo_line_rec.duration_expected
                    new_date_planned_start_wo = new_date_planned_start_wo - timedelta(minutes=duration_expected)
                    wo_line_rec.write({
                        'date_planned_start_wo': new_date_planned_start_wo,
                        'date_planned_finished_wo': end_date})


    def set_date_for_current_work_order(self):
        """
        Set Work Order Date with Previous Date
        """
        workorder_id = self.env.context.get('active_id', False)
        if workorder_id:
            workorder = self.env['mrp.workorder'].browse(workorder_id)
            new_date_planned_start_wo = self.new_date_planned_start_wo
            if workorder.state == 'progress':
                raise UserError(_('Midpoint Scheduling cannot be performed for workorder which is in progress.'))
            else:
                    duration_expected = workorder.duration_expected
                    end_date = new_date_planned_start_wo + timedelta(minutes=duration_expected)
                    workorder.write({
                        'date_planned_start_wo': new_date_planned_start_wo,
                        'date_planned_finished_wo': end_date})