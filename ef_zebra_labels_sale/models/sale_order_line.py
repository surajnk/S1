# -*- coding: utf-8 -*-
from odoo import models


def _num(value):
    return "%g" % (value or 0.0)


class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _inherit = ["sale.order.line", "zebra.label.mixin"]

    def _zebra_label_values(self):
        self.ensure_one()
        order = self.order_id
        size = "%sx%s" % (_num(self.x_customer_order_width), _num(self.x_customer_order_length))
        del_date = order.x_order_custom_del_date
        return {
            "customer": order.partner_id.name,
            "order_name": order.name,
            "part_desc": self.product_id.default_code,
            "ref1": self.x_ref1,
            "po": order.client_order_ref,
            "uom": self.x_order_customer_uom.name,
            "item_qty": _num(self.product_uom_qty),
            "size": size,
            "putups": _num(self.uom_put_up),
            "prod_date": del_date.strftime("%m/%d/%Y") if del_date else "",
            "embossing": self.x_order_line_embossing.display_name,
        }

    def action_print_zebra_label(self):
        return self.env["zebra.label.wizard"].open_for(self)
