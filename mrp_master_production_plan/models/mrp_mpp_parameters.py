# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProductSupplierinfo (models.Model):
    _inherit = "product.supplierinfo"

    is_subcontractor = fields.Boolean(store=True)


class MrpMppParameters (models.Model):
    _name = "mrp.mpp.parameters"
    _description = "MPP Planning Parameters"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    LOT_QTY_METHOD = [
        ('F', _('fixed order quantity')),
        ('L', _('lot for lot')),
        ('S', _('supply coverage days')),
        ]

    name = fields.Char('MPP Planning Parameters', compute='get_name', store=True)
    active = fields.Boolean(default=True)
    product_id = fields.Many2one('product.product', "Product", domain="[('bom_ids','!=',False),('bom_ids.active','=',True),('bom_ids.type','in',['normal', 'subcontract']),('type', '=', 'product'),'|',('company_id','=',False),('company_id','=',company_id)]", required=True)
    uom_id = fields.Many2one('uom.uom', "UoM", related='product_id.uom_id')
    warehouse_id = fields.Many2one('stock.warehouse', 'Warehouse', required=True, domain="[('manufacture_to_resupply', '=', 'True')]")
    user_id = fields.Many2one('res.users', string='MPP Planner', default=lambda self: self.env.user, required=True, tracking=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True, related='warehouse_id.company_id', store=True)
    bom_id = fields.Many2one('mrp.bom', 'Bill of Material', required=True, domain="""['&','|',('company_id', '=', False),('company_id', '=', company_id),'&','|',('product_id','=',product_id),'&',('product_tmpl_id.product_variant_ids','=',product_id),('product_id','=',False),('type', '!=', 'phantom')]""")
    bom_type = fields.Selection(string='BoM Type', store=True, related='bom_id.type')
    supplier_id = fields.Many2one('product.supplierinfo', 'Subcontractor')
    mpp_minimum_stock_qty = fields.Float("Safety Stock", group_operator=False)
    mpp_safety_time = fields.Integer("Safety Time", group_operator=False)
    lot_qty_method = fields.Selection(LOT_QTY_METHOD, 'Lot Quantity Method', default="L", required=True)
    mpp_coverage_days = fields.Integer("Days of Coverage", group_operator=False)
    mpp_fixed_order_qty = fields.Float("Fixed Qty", default=0.0, group_operator=False)
    mpp_multiple_order_qty = fields.Float("Multiple Qty", default=1.0, group_operator=False)

    sales_lead_time = fields.Integer('Planned Sales Delivery Lead Time', group_operator=False,
        help=_("The planned sales delivery lead time is the number days needed to deliver the material or service to the customer. An average value has to be specified. It is used mainly in Demand Management to determine the goods availability date"))
    total_lead_time = fields.Integer('Total Replenishment Lead Time', group_operator=False,
    help=_("The total replenishment lead time is the time needed before the product is completely available again, that is, after all BOM levels have been procured or produced. It is not calculated by the system, but defined in this field as the total of the in-house production time(s) and/or the planned delivery time(s) of the longest production path. For materials produced in-house, the replenishment lead time is to be taken into account in performing material availability checks in Master Production Plan Management. In an availability check where the system takes the replenishment lead time into consideration."))


    _sql_constraints = [
        ('check_unique', 'unique(product_id, warehouse_id)', 'MPP Planning Parameters heve been already created for this product and this warehouse!'),
    ]

    @api.depends('product_id','warehouse_id')
    def get_name(self):
        self.name = self.product_id.name + "/" +self.warehouse_id.name
        return True

    @api.constrains('sales_lead_time','total_lead_time', 'mpp_multiple_order_qty','mpp_minimum_stock_qty', 'mpp_safety_time', 'mpp_fixed_order_qty','mpp_coverage_days')
    def _check_mpp_parameters(self):
        if self.sales_lead_time < 0.0 or self.total_lead_time < 0.0 or self.mpp_multiple_order_qty < 0.0 or self.mpp_minimum_stock_qty < 0.0 or self.mpp_safety_time < 0.0 or self.mpp_fixed_order_qty < 0.0 or self.mpp_coverage_days < 0.0:
            raise UserError(_('planning parameters cannot be negative'))

    @api.constrains('lot_qty_method','mpp_fixed_order_qty', 'mpp_coverage_days')
    def _check_lot_method_parameters(self):
        if self.lot_qty_method == 'F' and not self.mpp_fixed_order_qty > 0.0:
            raise UserError(_('fixed lot quantity has to be positive'))
        if self.lot_qty_method == 'S' and not self.mpp_coverage_days > 0.0:
            raise UserError(_('supply coverage days parameter has to be positive'))

    @api.constrains('warehouse_id','bom_id')
    def _check_bom_id(self):
        if self.bom_id and self.warehouse_id and self.bom_id.type == 'normal' and self.bom_id.picking_type_id and not self.bom_id.picking_type_id.warehouse_id.id == self.warehouse_id.id:
            raise UserError(_('BoM not allowed; please check its operation type'))
