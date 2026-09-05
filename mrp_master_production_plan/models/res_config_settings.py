# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'


    number_maximum_lots = fields.Integer('Maximum number of lots', default=10, required=True)
    warehouse_id = fields.Many2one('stock.warehouse', 'Default Warehouse')
    supply_warehouse_id = fields.Many2one('stock.warehouse', 'Source Warehouse')

    @api.constrains('number_maximum_lots')
    def _check_number_maximum_lots(self):
        if self.number_maximum_lots <= 0:
            raise UserError(_('Negative values for maximum number of lots are not allowed'))
        return True


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"


    number_maximum_lots = fields.Integer('Maximum number of lots', related="company_id.number_maximum_lots", readonly=False)
    warehouse_id = fields.Many2one('stock.warehouse', related="company_id.warehouse_id", readonly=False)
    supply_warehouse_id = fields.Many2one('stock.warehouse', related="company_id.supply_warehouse_id", readonly=False)
