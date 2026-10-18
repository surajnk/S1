# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    wo_name = fields.Char("1st Workorder", readonly=True)
    x_pc_split = fields.Boolean(
        string='Split by Operation',
        copy=True,
        readonly=True,
        help="Pick Components transfer holding the components of one BOM "
             "operation. Its destination is that operation's workcenter "
             "location and is not forced to the first work order's.",
    )
    x_frame_no = fields.Char(string='Frame No')
    reverse_of_picking_id = fields.Many2one(
        'stock.picking',
        string='Reverse Of',
        readonly=True,
        copy=False,
    )

