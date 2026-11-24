# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .. import zpl_utils

BUILTIN_PLACEHOLDERS = {"copies"}


class ZebraLabelTemplate(models.Model):
    """A label layout (ZPL) for one model, optionally owned by one customer."""
    _name = "zebra.label.template"
    _description = "Zebra Label Template"
    _order = "model_name, sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, copy=False, help="Short unique reference, e.g. SHE570")
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    model_id = fields.Many2one(
        "ir.model", string="Model", required=True, ondelete="cascade", index=True,
        domain=[("transient", "=", False)], help="The model the label is printed from.",
    )
    model_name = fields.Char(related="model_id.model", store=True, readonly=True, index=True)
    partner_id = fields.Many2one(
        "res.partner", string="Customer", ondelete="cascade", index=True,
        help="Customer this label belongs to. Leave empty for a generic label of the model.",
    )
    partner_path = fields.Char(
        "Customer Field",
        help="Field path from a record of the model to its customer, e.g. order_id.partner_id. "
             "Used to preselect this label for the customer's records.",
    )
    zpl_body = fields.Text(
        "ZPL", required=True,
        help="Label ZPL without ^XA/^XZ. Use {{ name }} placeholders, defined in Variables.",
    )
    variable_ids = fields.One2many("zebra.label.template.variable", "template_id", string="Variables", copy=True)
    printer_id = fields.Many2one("zebra.printer", string="Default Printer")
    copies = fields.Integer("Default Copies", default=1)

    _sql_constraints = [("code_uniq", "unique(code)", "The template code must be unique.")]

    # -- configuration helpers ---------------------------------------------------------------
    @api.model
    def _partner_path_for_model(self, model_name):
        """Default customer field path of a model. Extend per module."""
        model = self.env.get(model_name)
        return "partner_id" if model is not None and "partner_id" in model._fields else False

    @api.onchange("model_id")
    def _onchange_model_id(self):
        if self.model_id and not self.partner_path:
            self.partner_path = self._partner_path_for_model(self.model_id.model)

    @api.constrains("zpl_body", "variable_ids")
    def _check_placeholders(self):
        for tpl in self:
            used = set(zpl_utils.placeholders(tpl.zpl_body)) - BUILTIN_PLACEHOLDERS
            missing = sorted(used - set(tpl.variable_ids.mapped("name")))
            if missing:
                raise ValidationError(
                    _("Placeholders without a variable in %s: %s") % (tpl.code, ", ".join(missing)))

    @api.constrains("partner_path", "partner_id", "model_id")
    def _check_partner_path(self):
        for tpl in self:
            if tpl.partner_id and not tpl.partner_path:
                raise ValidationError(_("Set the Customer Field so the label can be matched to records."))
            if tpl.partner_path:
                self._check_path(tpl.model_id.model, tpl.partner_path)

    @api.model
    def _check_path(self, model_name, path):
        """Raise ValidationError unless path is a chain of real fields of model_name."""
        model = self.env[model_name]
        segments = path.split(".")
        for i, seg in enumerate(segments):
            field = model._fields.get(seg)
            if field is None or seg.startswith("_"):
                raise ValidationError(_("'%s' is not a field of %s (in '%s').") % (seg, model._name, path))
            if i < len(segments) - 1:
                if not field.relational:
                    raise ValidationError(_("'%s' is not a relation, so '%s' cannot continue after it.") % (seg, path))
                model = self.env[field.comodel_name]

    def action_sync_variables(self):
        """Create a variable line for every placeholder of the ZPL that has none."""
        for tpl in self:
            known = set(tpl.variable_ids.mapped("name"))
            for name in zpl_utils.placeholders(tpl.zpl_body):
                if name not in known and name not in BUILTIN_PLACEHOLDERS:
                    # empty expression prints nothing until the field mapping is filled in
                    self.env["zebra.label.template.variable"].with_context(zebra_skip_check=True).create(
                        {"template_id": tpl.id, "name": name, "expression": ""})
        return True

    def action_create_print_action(self):
        """Add Action -> Print Label on the template's model (list and form views)."""
        Action = self.env["ir.actions.server"].sudo()
        for tpl in self:
            existing = Action.search([
                ("binding_model_id", "=", tpl.model_id.id), ("name", "=", "Print Label")])
            if not existing:
                Action.create({
                    "name": "Print Label",
                    "model_id": tpl.model_id.id,
                    "binding_model_id": tpl.model_id.id,
                    "state": "code",
                    "code": 'action = env["zebra.label.wizard"].open_for(records)',
                })
        return {
            "type": "ir.actions.client", "tag": "display_notification",
            "params": {"title": _("Done"), "type": "success",
                       "message": _("'Print Label' is now in the Action menu of the model.")},
        }

    # -- matching ----------------------------------------------------------------------------
    def _resolve(self, record, path):
        """Value of a dotted field path on record. Only real fields can be read."""
        value = record
        for seg in path.split("."):
            if not isinstance(value, models.BaseModel):
                raise UserError(_("Cannot read '%s' on %s.") % (path, record._name))
            if seg.startswith("_") or seg not in value._fields:
                raise UserError(_("'%s' is not a field of %s.") % (seg, value._name))
            value = value[:1][seg] if len(value) > 1 else value[seg]
        if isinstance(value, models.BaseModel):
            return value[:1].display_name if value else ""
        return value

    def _rank_for(self, record):
        """None if the template does not fit record, else a sort key (customer-specific first)."""
        self.ensure_one()
        if not self.partner_id:
            return (1, self.sequence, self.id)
        partner = self._resolve_partner(record)
        mine = self.partner_id.commercial_partner_id
        if partner and partner.commercial_partner_id == mine:
            return (0, self.sequence, self.id)
        return None

    def _resolve_partner(self, record):
        value = record
        for seg in (self.partner_path or "").split("."):
            if not seg or not isinstance(value, models.BaseModel) or seg not in value._fields:
                return self.env["res.partner"]
            value = value[:1][seg] if len(value) > 1 else value[seg]
        return value if getattr(value, "_name", None) == "res.partner" else self.env["res.partner"]

    @api.model
    def _best_for(self, records):
        """The template that fits every record best, or an empty recordset when they disagree."""
        candidates = self.search([("model_name", "=", records._name)])
        chosen = set()
        for rec in records:
            ranked = [(t._rank_for(rec), t) for t in candidates]
            ranked = sorted([x for x in ranked if x[0] is not None], key=lambda x: x[0])
            chosen.add(ranked[0][1].id if ranked else False)
        if len(chosen) == 1 and False not in chosen:
            return self.browse(chosen.pop())
        return self.browse()

    # -- rendering ---------------------------------------------------------------------------
    def _render(self, record, copies=1, overrides=None):
        """ZPL body (no ^XA/^XZ) for record."""
        self.ensure_one()
        if record._name != self.model_name:
            raise UserError(_("Template %s prints %s records, not %s.") % (self.code, self.model_name, record._name))
        values = {var.name: var._evaluate(record) for var in self.variable_ids}
        values.update(overrides or {})
        values["copies"] = max(int(copies or 1), 1)
        try:
            return zpl_utils.render(zpl_utils.normalize_body(self.zpl_body), values)
        except KeyError as e:
            raise UserError(_("Label %s needs values that are not defined: %s") % (self.code, e.args[0]))

    def print_record(self, record, printer, copies=1, overrides=None):
        self.ensure_one()
        printer.print_label(self._render(record, copies, overrides))


class ZebraLabelTemplateVariable(models.Model):
    _name = "zebra.label.template.variable"
    _description = "Zebra Label Template Variable"
    _order = "name"

    template_id = fields.Many2one("zebra.label.template", required=True, ondelete="cascade", index=True)
    model_name = fields.Char(related="template_id.model_name", readonly=True)
    name = fields.Char("Placeholder", required=True, help="Used in the ZPL as {{ name }}")
    expression = fields.Char(
        "Source",
        help="Field path(s) of the model in braces: {order_id.client_order_ref}, "
             "{product_uom_qty:%g}, {x_width:%g}x{x_length:%g}, {order_id.date_order:%m/%d/%Y}. "
             "Text outside the braces is printed as is.",
    )

    _sql_constraints = [("name_uniq", "unique(template_id, name)", "Placeholder names must be unique per template.")]

    @api.constrains("name")
    def _check_name(self):
        for var in self:
            if not var.name.isidentifier() or var.name in BUILTIN_PLACEHOLDERS:
                raise ValidationError(_("'%s' is not a valid placeholder name.") % var.name)

    @api.constrains("expression")
    def _check_expression(self):
        if self.env.context.get("zebra_skip_check"):
            return
        for var in self:
            for path in zpl_utils.expression_paths(var.expression):
                self.env["zebra.label.template"]._check_path(var.template_id.model_name, path)

    def _evaluate(self, record):
        self.ensure_one()
        try:
            return zpl_utils.expand(self.expression, lambda path: self.template_id._resolve(record, path))
        except ValueError as e:
            raise UserError(_("Variable %s: %s") % (self.name, e))
