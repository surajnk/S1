from odoo import models, fields, api


class ManufacturingWorkOrderFilterWizard(models.TransientModel):
    _name = 'manufacturing.workorder.filter.wizard'
    _description = 'Filter Manufacturing Work Orders Wizard'

    manufacture_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
        required=True
    )

    @api.onchange('manufacture_id')
    def _onchange_manufacture_id(self):
        self.workcenter_id = False
        return {
            'domain': {
                'workcenter_id': [('id', 'in', self.manufacture_id.workorder_ids.mapped('workcenter_id').ids)]
            }
        }


    workcenter_id = fields.Many2one(
        'mrp.workcenter',
        string='Work Center',
    )


    def action_search_workorders(self):
        self.ensure_one()
        domain = [('production_id', '=', self.manufacture_id.id)]
        if self.workcenter_id:
            domain.append(('workcenter_id', '=', self.workcenter_id.id))
        return {
            'name': 'Filtered Work Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder',
            'view_mode': 'tree,form',
            'views': [[self.env.ref('mrp.mrp_production_workorder_tree_view').id, 'list'], [self.env.ref('mrp.workcenter_line_kanban').id, 'kanban']],
            'search_view_id': self.env.ref('mrp.view_mrp_production_work_order_search').id,
            'context': {
                'default_production_id': self.manufacture_id.id,
                'default_workcenter_id': self.workcenter_id.id if self.workcenter_id else False,
                'search_default_production_id': self.manufacture_id.id,
                'search_default_workcenter_id': self.workcenter_id.id if self.workcenter_id else False,
            },
        }