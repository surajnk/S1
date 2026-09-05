
from odoo import api, fields, models, _


class ProductTemplateIn(models.Model):
    _inherit = 'account.account'

    
    # @api.model
    # def default_get(self, default_fields):
    #     res = super(ProductTemplateIn, self).default_get(default_fields)
    #     if self.env.user.branch_id:
    #         res.update({
    #             'branch_id' : self.env.user.branch_id.id or False
    #         })
    #     return res

    branch_id = fields.Many2one('res.branch', string="Branch")