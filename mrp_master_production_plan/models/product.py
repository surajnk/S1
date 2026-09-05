# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProductProduct (models.Model):
    _inherit = 'product.product'

    mpp_parameters_ids = fields.One2many("mrp.mpp.parameters", "product_id", "MPP Planning Parameters")
    mpp_parameters = fields.Integer('MPP Planning Parameters', compute="_get_mpp_parameters_count", store=True)
    sop_active = fields.Boolean("SOP Active", default=False)

    @api.depends("mpp_parameters_ids", "mpp_parameters_ids.active")
    def _get_mpp_parameters_count(self):
        mpp_parameters_obj = self.env['mrp.mpp.parameters']
        for product in self:
            if product.company_id:
                product.mpp_parameters = mpp_parameters_obj.search_count([
                    ('active', '=', True),
                    ('product_id', '=', product.id),
                    ('company_id', '=', product.company_id.id)])
            else:
                product.mpp_parameters = mpp_parameters_obj.search_count([
                    ('active', '=', True),
                    ('product_id', '=', product.id)])

    def get_sop_planning(self):
        self.ensure_one()
        return {
            'name': _('SOP Planning'),
            'res_model': 'mrp.sop.massive.planning.wizard',
            'type': 'ir.actions.act_window',
            'binding_model_id': 'product.product',
            'view_mode': 'form',
            'target': 'new',
        }
