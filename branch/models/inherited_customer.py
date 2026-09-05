# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class ResPartnerIn(models.Model):
    _inherit = 'res.partner'

    
    @api.model
    def default_get(self, default_fields):
        res = super(ResPartnerIn, self).default_get(default_fields)
        if self.env.user.branch_id:
            res.update({
                'branch_id' : self.env.user.branch_id.id or False
            })
        return res

    branch_id = fields.Many2one('res.branch', string="Branch")

    def _get_contact_name(self, partner, name):
        """
        Include street or street2 information in the contact name.
        """
        base_name = partner.commercial_company_name or partner.sudo().parent_id.name or ''
        street_info = partner.street2 or ''
        if street_info:
            return "%s, %s, %s" % (base_name, name, street_info)
        return "%s, %s" % (base_name, name)