# -*- coding: utf-8 -*-
from odoo import api, models


class ZebraLabelTemplate(models.Model):
    _inherit = "zebra.label.template"

    @api.model
    def _partner_path_for_model(self, model_name):
        if model_name == "sale.order.line":
            return "order_id.partner_id"
        return super()._partner_path_for_model(model_name)
