from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = "product.product"

    product_attachment = fields.Many2many('ir.attachment', string="Attachment")

    def get_x_fsc_display(self):
        self.ensure_one()
        selection = self._fields['x_FSC'].selection
        if callable(selection):
            selection = selection(self.env)
        return dict(selection).get(self.x_FSC, '')