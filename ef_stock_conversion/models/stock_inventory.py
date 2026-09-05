from odoo import models, fields, api


class StockInventory(models.Model):
    _inherit = 'stock.inventory'

    stock_conversion_id = fields.Many2one('stock.conversion', 'Stock Conversion')


class StockInventoryLine(models.Model):
    _inherit = 'stock.inventory.line'

    stock_conversion_id = fields.Many2one('stock.conversion', 'Stock Conversion')
    on_hand_value = fields.Float(string="On Hand Value", compute="compute_value")
    counted_value = fields.Float(string="Counted Value", compute="compute_value")
    difference_value = fields.Float(string="Difference Value", compute="compute_value")

    @api.depends('theoretical_qty', 'product_qty', 'difference_qty')
    def compute_value(self):
        for rec in self:
            rec.on_hand_value = rec.theoretical_qty * rec.product_id.standard_price
            rec.counted_value = rec.product_qty * rec.product_id.standard_price
            rec.difference_value = rec.difference_qty * rec.product_id.standard_price
