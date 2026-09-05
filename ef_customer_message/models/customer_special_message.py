from odoo import models, fields, api


class CustomerSpecialMessage(models.Model):
    _name = 'customer.special.message'
    _rec_name = 'description'
    _description = 'Customer Special Message'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    customer_id = fields.Many2one('res.partner', 'Customer', domain=[('customer_rank', '>', 0)], tracking=True)
    description = fields.Char('Description')
    message_type = fields.Selection([('all', 'All'),
                              ('commodity_class', 'Commodity Class'),
                              ('item_group', 'Item Group'),
                              ('product', 'Product'),
                              ('labor_item', 'Labor Item'),
                              ('embossing', 'Embossing')], default='all', string='Type', tracking=True)
    product_commodity_code_id = fields.Many2one('product.commodity.code', 'Product Commodity')
    product_item_group_id = fields.Many2one('product.item.group', 'Product Item Group')
    product_id = fields.Many2one('product.product', 'Product')
    labor_items_id = fields.Many2one('labor.items', 'Labor Item')
    embossing_id = fields.Many2one('product.embossing', 'Embossing')
    order_type = fields.Selection([('yards', 'Yards'),
                              ('sheets', 'Sheets'),
                              ('both', 'Both')], default='yards', string='Order Type', tracking=True)
    message_line = fields.One2many('customer.special.message.line', 'customer_special_message_id', 'Messages')
    ma_popup = fields.Boolean('MA Popup')
    ma_confirmation = fields.Boolean('MA Confirmation')
    ma_sales_order = fields.Boolean('MA Sales Order')
    ma_manufacturing_order = fields.Boolean('MA Manufacturing Order')
    ri_popup = fields.Boolean('RI Popup')
    ri_confirmation = fields.Boolean('RI Confirmation')
    ri_sales_order = fields.Boolean('RI Sales Order')
    ri_manufacturing_order = fields.Boolean('RI Manufacturing Order')


class CustomerSpecialMessageLine(models.Model):
    _name = 'customer.special.message.line'
    _description = 'Customer Special Message Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    customer_special_message_id = fields.Many2one('customer.special.message', 'Customer Special Message')
    name = fields.Char('Message')
