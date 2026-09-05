from odoo import api, fields, models

class ClassCode(models.Model):
    _name = 'class.code'
    _description = 'Class Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'x_class_code'

    x_class_code = fields.Char('Code')
    x_description = fields.Char('Description')