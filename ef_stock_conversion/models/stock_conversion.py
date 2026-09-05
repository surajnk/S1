from odoo import models, fields, api


class StockConversion(models.Model):
    _name = 'stock.conversion'
    _description = 'Stock Conversion'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Stock Conversion No', readonly=True, copy=False, default='New', tracking=True)
    created_by = fields.Many2one('res.users', 'Created By', default=lambda self: self.env.user, tracking=True)
    created_on = fields.Date('Created On', default=lambda self: fields.Datetime.now(), tracking=True)
    description = fields.Text('Description')
    stock_conversion_line = fields.One2many('stock.conversion.line', 'stock_conversion_id', 'Stock Conversion Line')
    state = fields.Selection([('draft', 'Draft'),
                              ('done', 'Done'),
                              ('cancel', 'Cancel')], default='draft', string='Status', tracking=True)
    stock_inventory_line_ids = fields.One2many('stock.inventory.line', 'stock_conversion_id', string="Stock Inventory Line", copy=False)
    count_stock_inventory_line = fields.Integer(compute='_count_stock_inventory_line', string="Inventory Lines")
    picking_id = fields.Many2one('stock.picking', string="Stock Picking")

    def _count_stock_inventory_line(self):
        for stock_conversion in self:
            stock_conversion.count_stock_inventory_line = self.env['stock.inventory.line'].search_count([('stock_conversion_id', '=', stock_conversion.id)])

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('stock.conversion') or 'New'
        res = super(StockConversion, self).create(vals)
        
        stock_inventory_line_ids = []
        for line in res.stock_conversion_line:
            stock_inventory_line_ids.append((0, 0, {
                'product_id': line.source_product_id.id,
                'product_uom_id': line.source_product_id.uom_id.id,
                'product_qty': line.source_product_id.qty_available - line.qty,
                'categ_id': line.source_product_id.categ_id.id,
                'location_id': line.source_location_id.id,
                'inventory_date': fields.datetime.now(),
                'stock_conversion_id': res.id,
            }))
            stock_inventory_line_ids.append((0, 0, {
                'product_id': line.destination_product_id.id,
                'product_uom_id': line.destination_product_id.uom_id.id,
                'product_qty': line.destination_product_id.qty_available + line.qty,
                'categ_id': line.destination_product_id.categ_id.id,
                'location_id': line.destination_location_id.id,
                'inventory_date': fields.datetime.now(),
                'stock_conversion_id': res.id,
           }))

        stock_inventory_id = self.env['stock.inventory'].create({
            'date': fields.datetime.now(),
            'name': 'Stock Conversion ' + str(res.name),
            'stock_conversion_id': res.id,
            'line_ids': stock_inventory_line_ids,
        })
        stock_inventory_id.action_start()
            
        return res

    def action_confirm(self):
        self.state = 'done'
        stock_inventory_ids = self.env['stock.inventory'].search([('stock_conversion_id', '=', self.id)])
        for stock_inventory_id in stock_inventory_ids:
            stock_inventory_id.action_validate()

    def action_cancel(self):
        self.state = 'cancel'
        stock_inventory_ids = self.env['stock.inventory'].search([('stock_conversion_id', '=', self.id)])
        for stock_inventory_id in stock_inventory_ids:
            stock_inventory_id.action_cancel_draft()


class StockConversionLine(models.Model):
    _name = 'stock.conversion.line'
    _description = 'Stock Conversion Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    stock_conversion_id = fields.Many2one('stock.conversion', 'Stock Conversion')
    source_product_id = fields.Many2one('product.product', 'Source Product', domain=[('type', '=', 'product')])
    source_location_id = fields.Many2one('stock.location', 'Source Location', domain=[('usage', '=', 'internal')])
    destination_product_id = fields.Many2one('product.product', 'Destination Product', domain=[('type', '=', 'product')])
    destination_location_id = fields.Many2one('stock.location', 'Destination Location', domain=[('usage', '=', 'internal')])
    qty = fields.Float('Qty')
    uom_id = fields.Many2one('uom.uom', 'UOM', related='source_product_id.uom_id', store=True)
