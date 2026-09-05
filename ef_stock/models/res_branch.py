from odoo import api, fields, models, _


class ResBranch(models.Model):
    _inherit = 'res.branch'

    # def get_default_address_to(self):
    #     """
    #     """
    #     print ('\n\n Get Default Address')
    #     print ('\n\n\n ===============')
    #     self.env.user.company_id.name

    address_to = fields.Text('Address From', default='Ecological Fibers')
