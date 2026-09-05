# models/auditlog_parent_ref.py
from odoo import api, fields, models

class AuditlogLog(models.Model):
    _inherit = 'auditlog.log'

    parent_model_id = fields.Many2one('ir.model', string='Parent Model', index=True)
    parent_model = fields.Char(string='Parent Technical Model', readonly=True)
    parent_res_id = fields.Integer('Parent Resource ID', index=True)
    parent_res_name = fields.Char('Parent Resource Name', readonly=True)
    parent_field_id = fields.Many2one('ir.model.fields', string='Parent Link Field', readonly=True)
    parent_field_name = fields.Char('Parent Link Field (technical)', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        logs = super().create(vals_list)
        for log in logs:
            vals = log._compute_parent_link_vals()
            if vals:
                super(AuditlogLog, log).write(vals)
        return logs

    def _compute_parent_link_vals(self):
        """Find a 'parent' Many2one on the logged record that is the inverse of
        a One2many from the parent model; return values to write on the log."""
        self.ensure_one()
        model = self.model_model or (self.model_id and self.model_id.model)
        res_id = self.res_id
        if not model or not res_id:
            return {}

        rec = self.env[model].browse(res_id)
        if not rec.exists():
            return {}

        # Collect candidate M2O fields that have a reverse O2M on the parent
        candidates = []
        for name, fld in rec._fields.items():
            if fld.type != 'many2one':
                continue
            parent_model = fld.comodel_name
            parent_fields = self.env[parent_model]._fields
            has_reverse = any(
                pf.type == 'one2many'
                and pf.comodel_name == rec._name
                and pf.inverse_name == name
                for pf in parent_fields.values()
            )
            if has_reverse:
                candidates.append((name, fld, rec[name]))

        if not candidates:
            return {}

        # Prefer common parent link names if present & non-empty
        preference = {
            'parent_id', 'order_id', 'move_id', 'picking_id', 'invoice_id',
            'sale_id', 'purchase_id', 'pricelist_id', 'product_pricelist_item_id'
        }
        chosen = None
        for pref in preference:
            for name, fld, val in candidates:
                if name == pref and val:
                    chosen = (name, fld, val)
                    break
            if chosen:
                break

        if not chosen:
            # otherwise first non-empty, else the first candidate
            chosen = next(((n, f, v) for n, f, v in candidates if v), candidates[0])

        name, fld, parent = chosen
        if not parent:
            return {}

        irm = self.env['ir.model'].search([('model', '=', fld.comodel_name)], limit=1)
        irmf = self.env['ir.model.fields'].search(
            [('model', '=', rec._name), ('name', '=', name)], limit=1
        )
        return {
            'parent_model_id': irm.id or False,
            'parent_model': fld.comodel_name,
            'parent_res_id': parent.id,
            'parent_res_name': parent.display_name,
            'parent_field_id': irmf.id or False,
            'parent_field_name': name,
        }


class AuditlogLogLine(models.Model):
    _inherit = 'auditlog.log.line'

    parent_model_id = fields.Many2one(related='log_id.parent_model_id', store=True)
    parent_model = fields.Char(related='log_id.parent_model', store=True)
    parent_res_id = fields.Integer(related='log_id.parent_res_id', store=True)
    parent_res_name = fields.Char(related='log_id.parent_res_name', store=True)
    parent_field_id = fields.Many2one(related='log_id.parent_field_id', store=True)
    parent_field_name = fields.Char(related='log_id.parent_field_name', store=True)
