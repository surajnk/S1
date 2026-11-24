# -*- coding: utf-8 -*-
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ZebraLabelWizard(models.TransientModel):
    _name = "zebra.label.wizard"
    _description = "Print Zebra Label"

    res_model = fields.Char(required=True)
    res_ids = fields.Char(required=True, help="JSON list of record ids")
    template_id = fields.Many2one("zebra.label.template", string="Label", required=True)
    printer_id = fields.Many2one(
        "zebra.printer", string="Printer", required=True,
        default=lambda self: self.env["zebra.printer"].search([], limit=1),
    )
    copies = fields.Integer("Copies", default=1, required=True)
    item_qty = fields.Float(
        "Item Quantity",
        help="Quantity printed on the label ({{ item_qty }}). Leave 0 to use the record's own quantity.",
    )

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if self.template_id.printer_id:
            self.printer_id = self.template_id.printer_id
        if self.template_id.copies:
            self.copies = self.template_id.copies

    @api.model
    def open_for(self, records):
        context = {
            "default_res_model": records._name,
            "default_res_ids": json.dumps(records.ids),
        }
        # preselect the customer's label when every record agrees on it
        template = self.env["zebra.label.template"]._best_for(records)
        if template:
            context["default_template_id"] = template.id
            if template.printer_id:
                context["default_printer_id"] = template.printer_id.id
            if template.copies:
                context["default_copies"] = template.copies
        return {
            "type": "ir.actions.act_window",
            "name": _("Print Label"),
            "res_model": self._name,
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def action_print(self):
        self.ensure_one()
        records = self.env[self.res_model].browse(json.loads(self.res_ids)).exists()
        if not records:
            raise UserError(_("Nothing to print."))
        if self.template_id.model_name != self.res_model:
            raise UserError(_("Label %s is not for these records.") % self.template_id.code)
        overrides = {"item_qty": "%g" % self.item_qty} if self.item_qty else None
        for rec in records:
            self.template_id.print_record(rec, self.printer_id, self.copies, overrides)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Label sent"),
                "message": _("%s sent to %s") % (self.template_id.code, self.printer_id.name),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
