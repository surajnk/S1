from odoo import fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    component_workorder_ids = fields.Many2many(
        comodel_name="mrp.workorder",
        relation="stock_move_component_workorder_rel",
        column1="move_id",
        column2="workorder_id",
        string="Work Orders",
        help="Work orders linked to this component move line.",
    )

    curr_comp = fields.Boolean(
        string="Curr Comp",
        default=False,
        help="Mark this component line as current component.",
    )


#     Boolean - will be enabled auto - if its part of BoM already - Jan 19 2026

# on edit and save , update the qty onto new component and the check for new workorders as well (without onchange of the master yards)
