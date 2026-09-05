from odoo import models, fields, api, _


class DepositionCode(models.Model):
    _name = "deposition.code"
    _description = "Deposition"
    _rec_name = "disposition_code"

    disposition_code = fields.Char('Disposition Code')

