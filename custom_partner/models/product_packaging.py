from odoo import models, fields, api

class ProductPackaging(models.Model):
    _inherit = 'product.packaging'

    is_mm = fields.Boolean(string='Is MM')
    display_name = fields.Char(string='Display Name')

    def name_get(self):
        result = []
        for record in self:
            name = record.name if record.name else ''
            dn = record.display_name if record.display_name else ''
            if dn:
                display_name = "%s [%s]" % (name, dn)
            else:
                display_name = "%s" % (name)
            result.append((record.id, display_name))
        return result


    @api.onchange('height', 'width', 'packaging_length', 'max_weight', 'is_mm')
    def _onchange_dimensions(self):
        if self.is_mm:
            w = f"{int(self.width)}mm"
            l = f"{int(self.packaging_length)}mm"
            wt = f"{self.max_weight:.2f}"
            self.display_name = f"{l} * {w} * {wt}"
        else:
            w = f"{int(self.width)}"
            l = f"{int(self.packaging_length)}"
            wt = f"{self.max_weight:.2f}"
            self.display_name = f"{l} * {w} * {wt}"



