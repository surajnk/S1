from odoo import api, fields, models

class AccountAccount(models.Model):
    _inherit = "account.account"


    x_location = fields.Selection([
        ('notfsc', 'NOT FSC'),
        ('fscmixcredit', 'FSC MIX CREDIT : NC-COC-003258'),
        ('fscrecycled', 'FSC RECYCLED 100% : NC-COC-003258'),
        ('fscrecycledcredit', 'FSC RECYCLED 100% : NC-COC-003258')], 'FSC')