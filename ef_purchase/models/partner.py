from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ResPartnerIn(models.Model):
    _inherit = 'res.partner'

    is_default_contact = fields.Boolean(string='Is Default Contact')

    @api.constrains('child_ids')
    def _onchange_child_ids(self):
        if self.child_ids:
            if len( self.child_ids) == 1:
                self.child_ids[0].is_default_contact = True
            else:
                default_contact_count = sum(child.is_default_contact for child in self.child_ids)
                if default_contact_count > 1:
                    raise ValidationError("Default is set already. Please Uncheck it")