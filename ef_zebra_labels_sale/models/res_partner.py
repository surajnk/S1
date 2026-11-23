# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    zebra_label_zpl = fields.Text(
        string="Zebra Label (ZPL)", copy=False,
        help="This customer's label as ZPL, printed from the sale order. Leave out ^XA/^XZ. "
             "Use placeholders such as {{ po }}, {{ size }}, {{ item_qty }}, {{ desc }}, "
             "{{ part_desc }}, {{ ref1 }}, {{ customer }}, {{ order_name }}, {{ uom }}, "
             "{{ putups }}, {{ prod_date }}, {{ embossing }}, {{ copies }}.",
    )
