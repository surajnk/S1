# -*- coding: utf-8 -*-
from odoo import models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def action_print_zebra_label(self):
        return self.env["zebra.label.wizard"].open_for(self)
