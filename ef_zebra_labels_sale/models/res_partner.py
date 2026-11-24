# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    zebra_label_template_ids = fields.One2many(
        "zebra.label.template", "partner_id", string="Zebra Labels", context={"active_test": False})
