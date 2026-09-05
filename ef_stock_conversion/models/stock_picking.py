from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    stock_conversion_ids = fields.One2many('stock.conversion', 'picking_id', string="Stock Conversion", copy=False)
    count_stock_conversion = fields.Integer(compute='_count_stock_conversion', string="Stock Conversions")
    code = fields.Selection(related='picking_type_id.code', string='Code', store=True)

    def _count_stock_conversion(self):
        for picking in self:
            picking.count_stock_conversion = len(picking.stock_conversion_ids)

    def action_view_stock_conversions(self, stock_conversions=False):
        if not stock_conversions:
            self.sudo()._read(['stock_conversion_ids'])
            stock_conversions = self.stock_conversion_ids

        action = self.env.ref('ef_stock_conversion.action_stock_conversion').sudo()
        result = action.read()[0]
        if len(stock_conversions) > 1:
            result['domain'] = [('id', 'in', stock_conversions.ids)]
        elif len(stock_conversions) == 1:
            res = self.env.ref('ef_stock_conversion.stock_conversion_form_view', False)
            form_view = [(res and res.id or False, 'form')]
            if 'views' in result:
                result['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                result['views'] = form_view
            result['res_id'] = stock_conversions.id
        else:
            result = {'type': 'ir.actions.act_window_close'}
        return result
