# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    zebra_label_code = fields.Selection(
        selection="_selection_zebra_label_code", string="Zebra Label", copy=False,
        help="Label preselected when printing labels for this customer's sale order lines.",
    )

    @api.model
    def _selection_zebra_label_code(self):
        return self.env["sale.order.line"]._zebra_label_codes()
