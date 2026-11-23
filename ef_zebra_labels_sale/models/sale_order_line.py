# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.ef_zebra_labels import zpl_utils

CUSTOMER_LABEL = "CUSTOMER"


def _num(value):
    return "%g" % (value or 0.0)


class SaleOrderLine(models.Model):
    _name = "sale.order.line"
    _inherit = ["sale.order.line", "zebra.label.mixin"]

    @api.model
    def _zebra_label_codes(self):
        codes = super()._zebra_label_codes()
        return [(CUSTOMER_LABEL, _("Customer label (from customer master)"))] + codes

    def _zebra_customer_zpl(self):
        self.ensure_one()
        partner = self.order_id.partner_id
        return partner.zebra_label_zpl or partner.commercial_partner_id.zebra_label_zpl or ""

    def _zebra_default_label_code(self):
        self.ensure_one()
        return CUSTOMER_LABEL if self._zebra_customer_zpl().strip() else False

    def _zebra_label_body(self, code):
        if code != CUSTOMER_LABEL:
            return super()._zebra_label_body(code)
        zpl = self._zebra_customer_zpl().strip()
        if not zpl:
            raise UserError(_("Customer %s has no label ZPL. Fill in 'Zebra Label (ZPL)' on the customer.")
                            % self.order_id.partner_id.display_name)
        return zpl_utils.normalize_body(zpl)

    def _zebra_label_values(self):
        self.ensure_one()
        order = self.order_id
        size = "%sx%s" % (_num(self.x_customer_order_width), _num(self.x_customer_order_length))
        del_date = order.x_order_custom_del_date
        return {
            "customer": order.partner_id.name,
            "order_name": order.name,
            "part_desc": self.product_id.default_code,
            "desc": self.product_id.name,
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
