# -*- coding: utf-8 -*-
# this module is made under odoo private license OPL-1

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime
import logging
from datetime import date


_logger = logging.getLogger(__name__)


class MaterialRequest(models.Model):
    _name = 'project.mrequest'
    _description = 'Material Request'
    _order = "date_of_request desc"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Code", required=True, copy=False,
                       readonly=True, index=True, default=lambda self: 'New')
    project_id = fields.Many2one(
        comodel_name='project.project', string="Project name")
    task_id = fields.Many2one(comodel_name='project.task', string="Task name")
    suggested_vendore = fields.Many2one(
        comodel_name="res.partner", string="Suggested vendore", )
    user_id = fields.Many2one(comodel_name='res.users',
                              string='Created by', readonly=True)
    date_of_request = fields.Datetime(
        string="Request date", default=fields.Datetime.now, readonly=True)
    date_deadline = fields.Datetime(
        string="deadline date", default=fields.Datetime.now, readonly=True)
    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Workcenter')
    production_id = fields.Many2one("mrp.production", "Manufacturing")
    mrequest_lines = fields.One2many(
        comodel_name='project.mrequest_lines', inverse_name='mrequest_id')
    state = fields.Selection(string="Status",
                             selection=[('draft', 'Draft'), ('request', 'Requested'), ('approve', 'Approved'),
                                        ('reject', 'Rejected'), ('quotation', 'Quotation requested'),
                                        ('delivery', 'Delivered'), ('done', 'done')],
                             required=False, default='draft')

    def draft(self):
        self.state = 'draft'

    def request(self):
        self.state = 'request'
        group_id = self.env.ref('mrequest.group_mrequest_manager').id
        summary = 'Approval is required for ' + self.name
        note = 'Approval is required for ' + self.name
        self.create_activity(self, group_id, summary, note)

    def reject(self):
        self.state = 'reject'
        group_id = self.env.ref('mrequest.group_mrequest_user').id
        summary = 'Request no. ' + self.name + 'rejected'
        note = 'Request no. ' + self.name + 'rejected'
        self.make_activity_done(self)

    def approve(self):
        self.state = 'approve'
        self.make_activity_done(self)
        group_id = self.env.ref(
            'mrequest.group_mrequest_purchase').id
        summary = 'Purchase is required for ' + self.name
        note = 'Purchase is required for ' + self.name
        self.create_activity(self, group_id, summary, note)

    def delivery(self):
        self.state = 'done'
        group_id = self.env.ref(
            'mrequest.group_mrequest_user').id
        summary = 'Material for ' + self.name + ' is ready for delivery'
        note = 'Material for ' + self.name + ' is ready for delivery'
        self.make_activity_done(self)
        self.create_activity(self, group_id, summary, note)

    def done(self):
        self.state = 'done'
        self.make_activity_done(self)

    @api.model
    def create_activity(self, res_model, group_id, summary, note):
        activity_to_do = self.env.ref('mail.mail_activity_data_todo').id
        res_group = self.env['res.groups'].search([('id', 'in', [group_id])])
        model_id = self.env['ir.model']._get('project.mrequest').id
        summary = summary
        note = note
        today = date.today()  # Ensure deadline is set to today
        for group in res_group:
            for user in group.users:
                values = {
                    'activity_type_id': activity_to_do,
                    'user_id': user.id,
                    'res_id': res_model.id,
                    'res_model_id': model_id,
                    'summary': summary,
                    'automated': True,
                    'note': note,
                    'date_deadline': today,  # <-- This makes it show under "Today"
                }
                activity = self.env['mail.activity'].create(values)

    def make_activity_done(self, res_id):
        res = self.env['mail.activity'].search(
            [('res_id', 'in', res_id.ids), ('res_model', '=', self._name), ])
        for act in res:
            act.sudo()._action_done()

    def create_rfq(self):
        lines = []
        if self.mrequest_lines:
            for line in self.mrequest_lines:
                lines.append((0, 0, {
                    'product_id': line.product.id,
                    'name': line.product.name,
                    'product_qty': line.quantity,
                    'price_unit': 0.0,
                    'date_planned': datetime.now(),
                    'product_uom': line.unit.id,

                }))
            self.env['purchase.order'].create({
                'partner_id': self.suggested_vendore.id,
                'date_order': datetime.now(),
                'mrequest_id': self.id,
                # 'project_id': self.project_id.id,
                # 'code': self.project_id.code,
                'order_line': lines
            })

    def action_view_mop_delivery(self):
        """ 
        This function returns an action that displays pickings related to
        manufacturing orders. It can either be in a list or in a form
        view, depending on the number of pickings.
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        pickings = self.production_id.mapped('picking_ids')
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif pickings:
            form_view = [(self.env.ref('stock.view_picking_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = pickings.id
        action['context'] = dict(self._context, default_origin=self.name, create=False)
        return action

    def get_po(self):
        action = self.env.ref("purchase.purchase_rfq").read()[0]
        action['views'] = [
            (self.env.ref('purchase.purchase_order_tree').id, 'tree'),
            (self.env.ref('purchase.purchase_order_form').id, 'form')]
        action['domain'] = [('mrequest_id', '=', self.id)]
        return action

    # serial number

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'project.mrequest') or 'New'
        return super(MaterialRequest, self).create(vals)

    @api.onchange('production_id')
    def onchange_production_id(self):
        """
        Onchange Production
        """
        self.mrequest_lines = False
        material_request_line = []
        for move_raw_rec in self.production_id.move_raw_ids:
            material_request_line.append((0, 0, {
                'product': move_raw_rec.product_id and move_raw_rec.product_id.id or False,
                'quantity': move_raw_rec.product_uom_qty,
                'done_quantity': move_raw_rec.quantity_done,
                'unit': move_raw_rec.product_uom
            }))
        self.mrequest_lines = material_request_line


class MaterialRequestLines(models.Model):
    _name = 'project.mrequest_lines'

    product = fields.Many2one(
        comodel_name='product.product', string='Product', required=True)
    description = fields.Char(string='Description', related='product.name')
    quantity = fields.Integer(string='Quantity', required=True)
    quantity_available = fields.Float(
        string="Quantity available", related='product.qty_available')
    unit = fields.Many2one('uom.uom',string='Unit')
    mrequest_id = fields.Many2one(
        comodel_name="project.mrequest")

    done_quantity = fields.Float(
    string="Done Quantity", compute="_compute_done_quantity", store=True)

    @api.depends('mrequest_id.production_id.picking_ids.move_ids_without_package.quantity_done')
    def _compute_done_quantity(self):
        for line in self:
            total_done = 0.0
            if line.mrequest_id.production_id:
                for picking in line.mrequest_id.production_id.picking_ids:
                    for move in picking.move_ids_without_package:
                        if move.product_id == line.product:
                            total_done += move.quantity_done
            line.done_quantity = total_done



class Purchase(models.Model):
    _inherit = 'purchase.order'

    mrequest_id = fields.Many2one(comodel_name="project.mrequest")
