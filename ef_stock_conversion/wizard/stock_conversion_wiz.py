from odoo import models, fields, api


class StockConversionWiz(models.TransientModel):
    _name = 'stock.conversion.wiz'
    _description = 'Stock Conversion Wiz'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def default_get(self, fields):
        rec = super(StockConversionWiz, self).default_get(fields)
        picking_obj = self.env['stock.picking'].browse(self._context.get('active_ids'))
        stock_conversion_list = []
        for stock_conversion in picking_obj.move_ids_without_package:
            stock_conversion_list.append((0, 0, {
                'source_product_id': stock_conversion.product_id.id,
                'destination_product_id': stock_conversion.product_id.x_product_conversion.id,
                'qty': stock_conversion.quantity_done,
            }))
        rec['stock_conversion_line'] = stock_conversion_list
        return rec

    created_by = fields.Many2one('res.users', 'Created By', default=lambda self: self.env.user, tracking=True)
    created_on = fields.Date('Created On', default=lambda self: fields.Datetime.now(), tracking=True)
    description = fields.Text('Description')
    stock_conversion_line = fields.One2many('stock.conversion.line.wiz', 'stock_conversion_wiz_id', 'Stock Conversion Line')

    def action_create_stock_conversion(self):
        picking_obj = self.env['stock.picking'].browse(self._context.get('active_ids'))

        stock_inventory_line_ids = []
        for line in self.stock_conversion_line:
            stock_inventory_line_ids.append((0, 0, {
                'source_product_id': line.source_product_id.id,
                'source_location_id': line.source_location_id.id,
                'destination_product_id': line.destination_product_id.id,
                'destination_location_id': line.destination_location_id.id,
                'qty': line.qty,
                'uom_id': line.uom_id.id
            }))

        stock_conversion_id = self.env['stock.conversion'].create({
            'description': self.description,
            'picking_id': picking_obj.id,
            'stock_conversion_line': stock_inventory_line_ids,
        })


class StockConversionLineWiz(models.TransientModel):
    _name = 'stock.conversion.line.wiz'
    _description = 'Stock Conversion Line Wiz'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    stock_conversion_wiz_id = fields.Many2one('stock.conversion.wiz', 'Stock Conversion Wizz')
    source_product_id = fields.Many2one('product.product', 'Source Product', domain=[('type', '=', 'product')])
    source_location_id = fields.Many2one('stock.location', 'Source Location', domain=[('usage', '=', 'internal')])
    destination_product_id = fields.Many2one('product.product', 'Destination Product', domain=[('type', '=', 'product')])
    destination_location_id = fields.Many2one('stock.location', 'Destination Location', domain=[('usage', '=', 'internal')])
    qty = fields.Float('Qty')
    uom_id = fields.Many2one('uom.uom', 'UOM', related='source_product_id.uom_id', store=True)
