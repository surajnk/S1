# -*- encoding: utf-8 -*-

from odoo import fields, models, api, _
# from odoo.exceptions import ValidationError
# import base64


class PackageImages(models.Model):
    _name = 'package.images'
    _description = 'Package Images'

    name = fields.Char(required=True)
    image = fields.Image(store=True)
    filename = fields.Char("File Name")
    quant_package_id = fields.Many2one('stock.quant.package', 'Package Id')
