from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math
import logging
import json

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = 'stock.move'

    x_conversion_product = fields.Boolean('Convert')
    x_to_product =  fields.Many2one('product.product','Conversion Product')

    @api.onchange('product_id','x_conversion_product')
    def onchange_product_conversion(self):
        if self.product_id and self.x_conversion_product:
            self.x_to_product = self.product_id.x_product_conversion
        else:
            self.x_to_product =     ''

class Location(models.Model):
    _inherit = 'stock.location'

    x_exclude_from_available = fields.Boolean(
        'Exclude from Available Qty',
        help="Stock in this location is not counted in the product Available column.")

    @api.onchange('location_id')
    def onchange_location(self):
        if self.location_id:
            self.branch_id = self.location_id.branch_id.id
        else:
            self.branch_id = 0



# class MrpFrames(models.Model):
#     _name = 'mrp.frames'
#     _rec_name = 'x_frame_id'

    
