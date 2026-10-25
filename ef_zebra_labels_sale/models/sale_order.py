# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_print_zebra_labels(self):
        self.ensure_one()
        return self.env["zebra.label.wizard"].open_for(self.order_line)
