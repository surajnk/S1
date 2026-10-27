# -*- coding: utf-8 -*-
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ZebraLabelWizard(models.TransientModel):
    _name = "zebra.label.wizard"
    _description = "Print Zebra Label"

    res_model = fields.Char(required=True)
    res_ids = fields.Char(required=True, help="JSON list of record ids")
    label_code = fields.Selection(selection="_selection_label_code", string="Label", required=True)
    printer_id = fields.Many2one(
        "zebra.printer", string="Printer", required=True,
        default=lambda self: self.env["zebra.printer"].search([], limit=1),
    )
    copies = fields.Integer("Copies", default=1, required=True)
    item_qty = fields.Float(
        "Item Quantity",
        help="Quantity printed on the label. Leave 0 to use the record's own quantity.",
    )

    @api.model
    def _selection_label_code(self):
        model = self.env.context.get("default_res_model")
        if model in self.env and hasattr(self.env[model], "_zebra_label_codes"):
            return self.env[model]._zebra_label_codes()
        # model unknown (e.g. while the views load): offer every label
        codes = {}
        for name in self.env.registry.models:
            if hasattr(self.env[name], "_zebra_label_codes") and name != "zebra.label.mixin":
                codes.update(dict(self.env[name]._zebra_label_codes()))
        return sorted(codes.items())

    @api.model
    def open_for(self, records):
        return {
            "type": "ir.actions.act_window",
            "name": _("Print Label"),
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": records._name,
                "default_res_ids": json.dumps(records.ids),
            },
        }

    def action_print(self):
        self.ensure_one()
        records = self.env[self.res_model].browse(json.loads(self.res_ids)).exists()
        if not records:
            raise UserError(_("Nothing to print."))
        if self.label_code not in dict(records._zebra_label_codes()):
            raise UserError(_("Label %s is not available for these records.") % self.label_code)
        overrides = {"item_qty": "%g" % self.item_qty} if self.item_qty else None
        records._zebra_print_label(self.label_code, self.printer_id, self.copies, overrides)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Label sent"),
                "message": _("%s sent to %s") % (self.label_code, self.printer_id.name),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
