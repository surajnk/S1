# -*- coding: utf-8 -*-
import os

from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.modules import get_module_path

from .. import zpl_utils


class ZebraLabelMixin(models.AbstractModel):
    """Give a model its own labels.

    Labels are .zpl files in ``<any module>/zpl/<model _name>/<CODE>.zpl``. A
    model that inherits this mixin only has to supply the values for the
    placeholders in those files by overriding ``_zebra_label_values``.
    """
    _name = "zebra.label.mixin"
    _description = "Zebra Label Mixin"

    @api.model
    def _zebra_label_files(self):
        """{code: (name, folder)} of the labels available for this model.

        Every installed module may ship ``zpl/<model _name>/<CODE>.zpl``; if
        two modules ship the same code, the later module (by name) wins.
        """
        modules = self.env["ir.module.module"].sudo().search(
            [("state", "=", "installed")], order="name").mapped("name")
        files = {}
        for module in modules:
            path = get_module_path(module, display_warning=False)
            if not path:
                continue
            folder = os.path.join(path, "zpl", self._name)
            for code, name in zpl_utils.list_labels(folder):
                files[code] = (name, folder)
        return files

    @api.model
    def _zebra_label_codes(self):
        """[(code, name)] of the labels available for this model."""
        return sorted((code, name) for code, (name, _folder) in self._zebra_label_files().items())

    def _zebra_label_values(self):
        """Placeholder values for one record. Override per model."""
        self.ensure_one()
        return {}

    def _zebra_render_label(self, code, copies=1, overrides=None):
        """Return the ZPL body (no ^XA/^XZ) for this record."""
        self.ensure_one()
        label = self._zebra_label_files().get(code)
        if not label:
            raise UserError(_("Label %s is not defined for %s.") % (code, self._description))
        body = zpl_utils.read_label(label[1], code)
        values = dict(self._zebra_label_values(), **(overrides or {}))
        values["copies"] = max(int(copies or 1), 1)
        try:
            return zpl_utils.render(body, values)
        except KeyError as e:
            raise UserError(_("Label %s needs values this record cannot supply: %s") % (code, e.args[0]))

    def _zebra_print_label(self, code, printer, copies=1, overrides=None):
        for rec in self:
            printer.print_label(rec._zebra_render_label(code, copies, overrides))
