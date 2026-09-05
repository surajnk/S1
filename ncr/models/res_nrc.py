from datetime import datetime

from odoo import models, fields, api, _
import json
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class ResNrc(models.Model):
    _name = "res.nrc"
    _inherit = ['mail.thread']
    _description = "NCR"
    _rec_name = "name"

    data_id = fields.One2many('nrc.data', 'nrc_id')
    name = fields.Char(string="Name", required=True, readonly=True, default=lambda self: _("New"))
    model_selection = fields.Selection(
        [("po", "PO"), ("mo", "MO"),('lot', 'Lot')],
        required=True,
        default="po",
    )
    purchase_id = fields.Many2one('purchase.order', string="Purchase Order")
    mrp_id = fields.Many2one('mrp.production', string="Manufacturing Order")
    created_by = fields.Many2one('res.users', string="Created by", default=lambda self: self.env.user, readonly=True)
    material_mo = fields.Many2one('product.product', string="Material", readonly=True)
    material_po = fields.Many2one('product.product', string="Material")
    product_domain = fields.Char(compute="_compute_product_domain", readonly=True, store=False, )
    mo_status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('progress', 'In Progress'),
        ('to_close', 'To Close'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')], string='MO State',

    )
    status = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed')], string='status', tracking=True, copy=False, default='open'

    )
    partner_id = fields.Many2one('res.partner', string="Customer")
    vendor_id = fields.Many2one('res.partner', string='Vendor Reference')
    work_id = fields.Many2one('mrp.workcenter', string='Area')

    defect_id = fields.Many2one('defect.master', string='Defect')
    defect_domain = fields.Char(compute="_compute_defect_domain", readonly=True, store=False, )
    operation_id = fields.Many2one('mrp.workorder', string="Operation")
    operation_id_domain = fields.Char(compute="_compute_operation_id", readonly=True, store=False, )
    x_pattern_wo = fields.Many2one(
        'product.embossing', 'Pattern', store=True, readonly=True)
    sample_provided = fields.Boolean(string="Sample Provided")
    order_pulled = fields.Boolean(string="Order Pulled")
    assignee = fields.Many2one('res.users', string="Assignee")
    closed_by = fields.Many2one('res.users', string="Closed By")
    deposition_by = fields.Many2one('res.users', string="Disposition By", tracking=True)
    deposition_code = fields.Many2one('deposition.code', string="Disposition Code")
    assignee_domain = fields.Char(compute="_compute_assign_domain", readonly=True, store=False, )
    warehouse_ncr_id = fields.Char('Warehouse')
    lot_ids = fields.One2many('ncr.lot', 'ncr_id')
    lot_ids_multiple = fields.One2many('nrc.stock.lot', 'nrc_id', string="Inventory Lots")

    @api.onchange('model_selection', 'purchase_id', 'mrp_id')
    def onchange_model_selection(self):
        self.lot_ids = False

    def close_ncr(self):
        for rec in self:
            rec.status = 'closed'
            rec.closed_by = self.env.user.id

    def send_ncr(self):
        for rec in self:
            template_id = self.env['ir.model.data'].xmlid_to_res_id('ncr.ncr_template_email', raise_if_not_found=False)
            template_final = self.env['mail.template'].browse(template_id)
            if template_id:
                if self.assignee:
                    template_final.sudo().send_mail(self.id, force_send=True)
                else:
                    raise UserError(_('Please select Assignee'))

    @api.depends('mrp_id', 'operation_id')
    def _compute_operation_id(self):
        for rec in self:
            rec.operation_id_domain = json.dumps(
                [('id', 'in', self.mrp_id.workorder_ids.ids)]
            )

    @api.depends('assignee')
    def _compute_assign_domain(self):
        for rec in self:
            rec.assignee_domain = json.dumps(
                [('id', 'in',
                  self.env['res.users'].search([]).filtered(lambda x: x.has_group('ncr.group_ncr_user')).ids)]
            )

    @api.onchange('mrp_id', 'operation_id')
    def onchange_mrp_operataion(self):
        self.work_id = self.operation_id.workcenter_id.id

    @api.depends('defect_id', 'work_id')
    def _compute_defect_domain(self):
        for rec in self:
            rec.defect_domain = json.dumps(
                [('id', 'in', self.env['defect.master'].search([('work_id', '=', self.work_id.id)]).ids)]
            )

    @api.onchange('operation_id')
    def onchange_operation_id(self):
        for rec in self:
            rec.x_pattern_wo = rec.operation_id.x_pattern_wo.id

    @api.onchange('purchase_id')
    def onchange_purchase_id(self):
        for rec in self:
            rec.material_po = False
            rec.vendor_id = rec.purchase_id.partner_id.id
            rec.warehouse_ncr_id = rec.purchase_id.picking_type_id.warehouse_id.name

    @api.onchange('mrp_id')
    def onchange_mrp_id(self):
        for rec in self:
            rec.material_mo = rec.mrp_id.product_id
            rec.mo_status = rec.mrp_id.state
            rec.warehouse_ncr_id = rec.mrp_id.picking_type_id.warehouse_id.name
            rec.partner_id = self.env['sale.order'].search([('name', '=', rec.mrp_id.origin)]).partner_id.id

    @api.depends('material_po', 'purchase_id')
    def _compute_product_domain(self):
        for rec in self:
            rec.product_domain = json.dumps(
                [('id', 'in', self.purchase_id.order_line.mapped('product_id').ids)]
            )

    @api.model
    def create(self, vals):
        vals["name"] = self.env["ir.sequence"].next_by_code("res.nrc") or _("New")
        res = super(ResNrc, self).create(vals)
        return res


class NcrLot(models.Model):
    _name = "ncr.lot"

    ncr_id = fields.Many2one('res.nrc', string='NCR')
    lot_details = fields.Many2one('mrp.wo.roll.line', string="Lot Detail")
    lot_details_domain = fields.Char(compute="_compute_lot_details_domain", readonly=True, store=False, )
    lot_po_details = fields.Many2one('stock.production.lot', string="Lot Detail")
    lot_po_details_domain = fields.Char(compute="_compute_lot_po_details_domain", readonly=True, store=False, )
    qty = fields.Integer(string="Qty")

    @api.depends('lot_details', 'ncr_id.operation_id')
    def _compute_lot_details_domain(self):
        for rec in self:
            rec.lot_details_domain = json.dumps(
                [('id', 'in', self.ncr_id.operation_id.roll_line_ids.ids)]
            )

    @api.depends('lot_po_details', 'ncr_id.purchase_id')
    def _compute_lot_po_details_domain(self):
        for rec in self:
            rec.lot_po_details_domain = json.dumps(
                [('id', 'in', rec.ncr_id.purchase_id.picking_ids.mapped('move_ids_without_package').mapped(
                    'move_line_nosuggest_ids').mapped('lot_id').ids)]
            )

    @api.onchange('lot_po_details')
    def onchange_lot_po_details(self):
        for rec in self:
            rec.qty = rec.lot_po_details.product_qty

    @api.onchange('lot_details')
    def onchange_lot_details(self):
        for rec in self:
            rec.qty = rec.lot_details.quantity


class NrcData(models.Model):
    _name = "nrc.data"

    nrc_id = fields.Many2one('res.nrc', string='NCR')
    date_entry = fields.Datetime(string="Date / Time stamped commentary", default=fields.Datetime.now)

    data_selection = fields.Selection([
        ('problem', 'Problem'),
        ('actions', 'Actions'),
        ('disposition', 'Disposition'),
        ('misc', 'Misc'),
        ('accounting', 'Accounting')], string='Data Selection', default="problem"

    )
    remarks = fields.Char('Remarks')

class NrcStockLot(models.Model):
    _name = "nrc.stock.lot"
    _description = "NCR Stock Lot"

    nrc_id = fields.Many2one('res.nrc', string="NCR Reference")
    stock_lot_id = fields.Many2one('stock.production.lot', string="Stock Lot")
    stock_lot_id_domain = fields.Char(compute="_compute_stock_lot_id_domain", readonly=True, store=False)
    quantity = fields.Float(string="Quantity")
    product_id = fields.Many2one(string="Product", related='stock_lot_id.product_id')
    actual_quantity = fields.Float(string="Actual Quantity", related='stock_lot_id.product_qty')

    # @api.depends('stock_lot_id', 'ncr_id.purchase_id', 'ncr_id.mrp_id')
    # def _compute_stock_lot_id_domain(self):
    #     for rec in self:
    #         if self.nrc_id.purchase_id:
    #             lots = self.nrc_id.purchase_id.picking_ids.mapped('move_ids_without_package').mapped(
    #                 'move_line_nosuggest_ids').mapped('lot_id').ids
    #         elif self.nrc_id.mrp_id:
    #             lots = self.nrc_id.mrp_id.picking_ids.mapped('move_ids_without_package').mapped(
    #                 'move_line_nosuggest_ids').mapped('lot_id').ids
    #         else:
    #             lots = []
    #         rec.stock_lot_id_domain = json.dumps(
    #             [('id', 'in', lots)]
    #         )

    @api.depends('stock_lot_id', 'nrc_id.purchase_id', 'nrc_id.mrp_id')
    def _compute_stock_lot_id_domain(self):
        for rec in self:
            if rec.nrc_id.purchase_id:
                lots = rec.nrc_id.purchase_id.picking_ids.mapped('move_ids_without_package').mapped(
                    'move_line_nosuggest_ids').mapped('lot_id').ids
            elif rec.nrc_id.mrp_id:
                lots = rec.nrc_id.mrp_id.picking_ids.mapped('move_ids_without_package').mapped(
                    'move_line_ids').mapped('lot_id').ids
            else:
                lots = self.env['stock.production.lot'].search([]).ids
            rec.stock_lot_id_domain = json.dumps([('id', 'in', lots)])


class ProductProduct(models.Model):
    _inherit = 'product.product'

    nrc_quantity = fields.Float(string="NCR Quantity", compute='_compute_nrc_quantity', store=False)

    def _compute_nrc_quantity(self):
        nrc_model = self.env['res.nrc']
        for product in self:
            total_qty = 0.0
            all_nrcs = nrc_model.search([])
            for nrc in all_nrcs:
                # Filter lot lines that match the current product
                matching_lots = nrc.lot_ids_multiple.filtered(lambda l: l.product_id.id == product.id)
                total_qty += sum(matching_lots.mapped('quantity'))
            product.nrc_quantity = total_qty


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    nrc_quantity = fields.Float(
        string="NCR Quantity",
        compute='_compute_nrc_quantity',
        digits='Product Unit of Measure',
    )

    def _compute_nrc_quantity(self):
        lot_lines = self.env['nrc.stock.lot'].search([
            ('stock_lot_id', 'in', self.ids),
            ('nrc_id.status', '=', 'open'),      # drop if closed NCRs should count
        ])
        qty_map = {}
        for nl in lot_lines:
            qty_map[nl.stock_lot_id.id] = qty_map.get(nl.stock_lot_id.id, 0.0) + nl.quantity
        for lot in self:
            lot.nrc_quantity = qty_map.get(lot.id, 0.0)

    def action_view_ncr_details(self):
        self.ensure_one()
        wizard = self.env['on.order.detail.wizard'].create({})
        wizard._populate_lot_ncr_lines(self.id)
        return {
            'name': 'NCR - %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'on.order.detail.line',
            'view_mode': 'tree',
            'domain': [('wizard_id', '=', wizard.id)],
            'context': {'group_by': 'order_type'},
            'target': 'new',
        }