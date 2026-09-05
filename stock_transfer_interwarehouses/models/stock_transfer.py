# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockTransfer(models.Model):
    _name = 'stock.transfer'
    _description = 'Stock Transfer Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date desc, id desc'


    STOCK_TRANSFER_STATES = [
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('progress', 'In Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ]

    TRANSFER_STATES = [
        ('initial', 'Initial'),
        ('progress', 'In Progress'),
        ('done', 'Done'),
    ]

    READONLY_STATES = {
        'confirm': [('readonly', True)],
        'progress': [('readonly', True)],
        'done': [('readonly', True)],
        'cancel': [('readonly', True)],
    }

    name = fields.Char('Name', copy=False, required=True, readonly=True, default="New")
    user_id = fields.Many2one('res.users', string='Responsible', index=True, required=True, tracking=True, default=lambda self: self.env.user, check_company=True, states=READONLY_STATES)
    approval = fields.Boolean('Approval',  compute='_get_approval_needed', store=True)
    sent = fields.Boolean('sent status')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, states=READONLY_STATES, default=lambda self: self.env.company.id)
    stock_transfer_lines = fields.One2many('stock.transfer.line', 'stock_transfer_id', string='Stock Transfer Lines', copy=True)
    state = fields.Selection(STOCK_TRANSFER_STATES, string='Status', readonly=True, index=True, copy=False, default='draft', tracking=True)
    transfer_state = fields.Selection(TRANSFER_STATES, string=' Transfer Status', compute='_get_transfer_states', store=True)
    group_id = fields.Many2one('procurement.group', 'Procurement Group', states=READONLY_STATES, copy=False)
    active = fields.Boolean('Active', default=True)
    origin = fields.Char('Source Document', copy=False, states=READONLY_STATES)
    priority = fields.Selection(
        [('0', 'Normal'), ('1', 'Urgent')], 'Priority', default='0', index=True)
    notes = fields.Text('Notes', states=READONLY_STATES)

    warehouse_id = fields.Many2one('stock.warehouse', 'Destination Warehouse', check_company=True, required=True, states=READONLY_STATES)
    location_id = fields.Many2one('stock.location', 'Destination Location', compute='_get_locations')
    source_warehouse_id = fields.Many2one('stock.warehouse', 'Source Warehouse',  check_company=True, required=True, states=READONLY_STATES)
    source_location_id = fields.Many2one('stock.location', 'Source Location', compute='_get_locations')

    date = fields.Datetime('Document Date', required=True, states=READONLY_STATES, index=True, copy=False, default=fields.Datetime.now)
    date_planned = fields.Datetime('Receipt Date', index=True, copy=False, states=READONLY_STATES, default=fields.Datetime.now)
    picking_count = fields.Integer('Picking count', compute='_compute_picking', default=0, store=True)
    picking_ids = fields.Many2many('stock.picking', string='Picking', compute='_compute_picking', copy=False, store=True)


    @api.depends('create_uid', 'write_uid', 'user_id')
    def _get_approval_needed(self):
        for transfer in self:
            transfer.approval = False
            current_user_id = transfer.write_uid or transfer.create_uid
            if current_user_id == transfer.user_id:
                transfer.approval = True

    def send_approval_email(self):
        for transfer in self:
            template_id = self.env.ref('stock_transfer_interwarehouses.mail_template_data_stock_request_approval').id
            transfer.with_context(force_send=True).message_post_with_template(template_id, email_layout_xmlid='stock_transfer_interwarehouses.mail_stock_transfer_approval_request')
            transfer.sent = True


    @api.model
    def _create_sequence(self, vals):
        if not vals.get('name') or vals.get('name') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('stock.transfer') or 'New'
        return vals

    @api.model
    def create(self, vals):
        vals = self._create_sequence(vals)
        stocktransfer = super().create(vals)
        return stocktransfer

    @api.depends('group_id', 'state')
    def _compute_picking(self):
        for transfer in self:
            pickings = self.env['stock.picking'].search([('group_id', '=', transfer.group_id.id)])
            transfer.picking_ids = pickings
            transfer.picking_count = len(pickings)

    def action_view_picking(self):
        result = self.env["ir.actions.actions"]._for_xml_id('stock.action_picking_tree_all')
        pick_ids = self.mapped('picking_ids')
        if not pick_ids or len(pick_ids) > 1:
            result['domain'] = "[('id','in',%s)]" % (pick_ids.ids)
        elif len(pick_ids) == 1:
            res = self.env.ref('stock.view_picking_form', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + [(state,view) for state,view in result['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = pick_ids.id
        return result

    def unlink(self):
        for transfer in self:
            if not transfer.state == 'cancel':
                raise UserError(_('it is possible to delete a stock transfer document in state cancel only.'))
        return super().unlink()

    @api.depends('warehouse_id', 'source_warehouse_id')
    def _get_locations(self):
        for transfer in self:
            if transfer.warehouse_id and transfer.source_warehouse_id:
                transfer.source_location_id = transfer.source_warehouse_id.lot_stock_id.id
                transfer.location_id = transfer.warehouse_id.lot_stock_id.id
                if transfer.warehouse_id.reception_steps != "one_step":
                    transfer.location_id = transfer.warehouse_id.wh_input_stock_loc_id.id

    def _create_group_id(self):
        if not self.group_id:
            self.group_id = self.group_id.create({'name': self.name})
        return True

    def check_warehouses(self):
        if self.warehouse_id and self.source_warehouse_id and self.warehouse_id == self.source_warehouse_id:
            raise UserError(_('Source Warehouse cannot be Destination Warehouse also.'))

    def button_confirm(self):
        for transfer in self:
            transfer.check_warehouses()
            if not transfer.stock_transfer_lines:
                raise UserError(_('No line has been entered.'))
            if not transfer.group_id:
                transfer._create_group_id()
            for line in transfer.stock_transfer_lines:
                line._get_route()
                line.run_procurement()
            transfer.write({'state': 'confirm'})
        return True

    def button_draft(self):
        for transfer in self:
            pickings = transfer.picking_ids.filtered(lambda r: r.state != 'cancel')
            if pickings:
                pickings.action_cancel()
            transfer.write({'state': 'draft'})
            transfer.sent = False
        return True

    @api.depends('picking_ids.state')
    def _get_transfer_states(self):
        for transfer in self:
            transfer.transfer_state = 'initial'
            pickings = transfer.picking_ids.filtered(lambda r: r.state != 'cancel')
            if pickings and any(picking.state == 'done' for picking in pickings):
                transfer.transfer_state = 'progress'
            if pickings and all(picking.state == 'done' for picking in pickings):
                transfer.transfer_state = 'done'
        return True

    @api.constrains('transfer_state')
    def _get_states(self):
        for transfer in self:
            if transfer.transfer_state == 'progress':
                transfer.write({'state': 'progress'})
            if transfer.transfer_state == 'done':
                transfer.write({'state': 'done', 'priority': '0'})
        return True

    def button_cancel(self):
        self.write({'state': 'cancel'})
        return True
