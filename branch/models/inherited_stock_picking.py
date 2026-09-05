# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import Warning
from lxml import etree
from odoo.osv import expression
try:
    import json
except ImportError:
    import simplejson as json
from odoo import api, models, tools


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(StockPicking, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)

        if view_type in ('tree', 'form', 'kanban') and self.env.user.has_group(
                'ef_sales.group_sales_cust_rep'):
            arch = etree.XML(result['arch'])
            for node in arch.xpath("//tree | //form | //kanban"):
                node.set('create', 'false')
                node.set('edit', 'false')
                node.set('delete', 'false')
                result['arch'] = etree.tostring(arch)
        return result

    @api.model
    def default_get(self, default_fields):
        res = super(StockPicking, self).default_get(default_fields)
        if self.env.user.branch_id:
            res.update({
                'branch_id' : self.env.user.branch_id.id or False
            })
        return res

    branch_id = fields.Many2one('res.branch', string="Branch")

    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        selected_brach = self.branch_id
        if selected_brach:
            user_id = self.env['res.users'].browse(self.env.uid)
            user_branch = user_id.sudo().branch_id
            if user_branch and user_branch.id != selected_brach.id:
                raise Warning("Please select active branch only. Other may create the Multi branch issue. \n\ne.g: If you wish to add other branch then Switch branch from the header and set that.")