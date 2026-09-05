# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    (header kept as in your original file)
#
#############################################################################

import json
import logging
from lxml import etree

from odoo import api, models

_logger = logging.getLogger(__name__)


class HideFieldBase(models.AbstractModel):
    _inherit = 'base'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        """Hide selected fields for the *current* user on all views."""
        res = super(HideFieldBase, self).fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu,
        )

        # ❌ Never hide anything for the main Admin user
        admin_user = self.env.ref('base.user_admin', raise_if_not_found=False)
        if admin_user and self.env.user.id == admin_user.id:
            return res

        # Fields to hide for the currently logged-in user, for this model
        user_hidden_fields = self.env.user.sudo().hide_field_ids.filtered(
            lambda f: f.model == self._name
        )
        if not user_hidden_fields:
            return res

        field_names = user_hidden_fields.mapped('name')
        _logger.debug(
            "HideFieldBase: user %s (%s) hiding fields %s on model %s (view_type=%s)",
            self.env.user.id,
            self.env.user.login,
            field_names,
            self._name,
            view_type,
        )

        try:
            arch = etree.fromstring(res['arch'])
        except Exception as e:
            _logger.error("HideFieldBase: error parsing arch for model %s: %s", self._name, e)
            return res

        for field_name in field_names:
            # Hide <field name="...">
            for node in arch.xpath("//field[@name='%s']" % field_name):
                modifiers = json.loads(node.get('modifiers', '{}'))
                modifiers['invisible'] = True
                node.set('invisible', '1')
                node.set('modifiers', json.dumps(modifiers))

            # Also hide labels <label for="..."> if present
            for label in arch.xpath("//label[@for='%s']" % field_name):
                modifiers = json.loads(label.get('modifiers', '{}'))
                modifiers['invisible'] = True
                label.set('invisible', '1')
                label.set('modifiers', json.dumps(modifiers))

        res['arch'] = etree.tostring(arch, encoding='unicode')
        return res
