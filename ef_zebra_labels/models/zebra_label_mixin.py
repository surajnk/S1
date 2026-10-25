# -*- coding: utf-8 -*-
from odoo import _, api, models
from odoo.exceptions import UserError
from odoo.modules import get_module_path

from .. import zpl_utils


class ZebraLabelMixin(models.AbstractModel):
    """Give a model its own labels.

    Labels are .zpl files in ``zpl/<model _name>/<CODE>.zpl``. A model that
    inherits this mixin only has to supply the values for the placeholders in
    those files by overriding ``_zebra_label_values``.
    """
    _name = "zebra.label.mixin"
    _description = "Zebra Label Mixin"

    @api.model
    def _zebra_label_dirs(self):
        """Folders searched for this model's labels; other modules can extend."""
        return [
            "%s/zpl/%s" % (get_module_path("ef_zebra_labels"), self._name),
        ]

    @api.model
    def _zebra_label_codes(self):
        """[(code, name)] of the labels available for this model."""
        codes = {}
        for directory in self._zebra_label_dirs():
            codes.update(dict(zpl_utils.list_labels(directory)))
        return sorted(codes.items())

    def _zebra_label_values(self):
        """Placeholder values for one record. Override per model."""
        self.ensure_one()
        return {}

    def _zebra_render_label(self, code, copies=1, overrides=None):
        """Return the ZPL body (no ^XA/^XZ) for this record."""
        self.ensure_one()
        body = None
        for directory in reversed(self._zebra_label_dirs()):
            try:
                body = zpl_utils.read_label(directory, code)
                break
            except ValueError:
                continue
        if body is None:
            raise UserError(_("Label %s is not defined for %s.") % (code, self._description))
        values = dict(self._zebra_label_values(), **(overrides or {}))
        values["copies"] = max(int(copies or 1), 1)
        try:
            return zpl_utils.render(body, values)
        except KeyError as e:
            raise UserError(_("Label %s needs values this record cannot supply: %s") % (code, e.args[0]))

    def _zebra_print_label(self, code, printer, copies=1, overrides=None):
        for rec in self:
            printer.print_label(rec._zebra_render_label(code, copies, overrides))
