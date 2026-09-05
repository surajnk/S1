# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round
from lxml import etree
from odoo.osv import expression
try:
    import json
except ImportError:
    import simplejson as json
from odoo import api, models, tools

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    is_printed_mrp_production_report = fields.Char()


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(MrpProduction, self).fields_view_get(view_id, view_type, toolbar=toolbar, submenu=submenu)

        if view_type in ('tree', 'form', 'kanban') and self.env.user.has_group(
                'ef_sales.group_sales_cust_rep'):
            arch = etree.XML(result['arch'])
            for node in arch.xpath("//tree | //form | //kanban"):
                node.set('create', 'false')
                node.set('edit', 'false')
                node.set('delete', 'false')
                result['arch'] = etree.tostring(arch)
        return result


