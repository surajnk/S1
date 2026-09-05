# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MrpWorkCenterProductivity(models.Model):
    _inherit = 'mrp.workcenter.productivity'

    duration = fields.Float(_('Elapsed'))

    setup_duration = fields.Float('Setup Duration')
    teardown_duration = fields.Float('Teardown Duration')
    working_duration = fields.Float('Working Duration')
    overall_duration = fields.Float('Overall Duration')
    produce_quantity = fields.Float(string='Produce Quantity')
    # roll_id = fields.Many2one('mrp.production.roll', 'Roll Id')
    status = fields.Selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')], default="draft", tracking=True)
    components_id = fields.Many2one('product.product', "Component")
    process_by_id = fields.Many2one('res.users', 'Processed By')
    next_work_order_id = fields.Many2one('mrp.workorder', "Next Work Order", related="workorder_id.next_work_order_id")
    next_work_center_id = fields.Many2one('mrp.workcenter', "Next Work Center", related="next_work_order_id.workcenter_id",store=True)

    def action_in_progress(self):
        """
        Action In Progress
        """
        for rec in self:
            rec.process_by_id = self.env.user and self.env.user.id
            rec.status = 'in_progress'

    def action_done(self):
        """
        Action Done
        """
        for rec in self:
            rec.process_by_id = self.env.user and self.env.user.id
            rec.status = 'done'

    def action_draft(self):
        """
        Action Draft
        """
        for rec in self:
            rec.process_by_id = False
            rec.status = 'draft'
