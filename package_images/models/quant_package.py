# -*- encoding: utf-8 -*-

from odoo import fields, models, api, _


class StockQuantPackage(models.Model):
    _inherit = 'stock.quant.package'

    package_image_ids = fields.One2many('package.images', 'quant_package_id')
    x_height = fields.Integer(string='Height')
    x_width = fields.Integer(string='Width')
    x_length = fields.Integer(string='Length')

    def action_view_package_image(self):
        """
        """
        return {
            'type': 'ir.actions.act_window',
            'name': 'Package Images',
            'view_mode': 'kanban,tree,form',
            'res_model': 'package.images',
            'domain': [['id', 'in', self.package_image_ids.ids]],
            'context': {'default_quant_package_id': self.id}
        }