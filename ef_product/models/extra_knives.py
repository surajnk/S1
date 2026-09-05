from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
import re

class ExtraKnives(models.Model):
    _name = 'extra.knives'
    _description = 'Extra Knives'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    #_rec_name = 'x_extra_knives'

    name = fields.Char('Knives Name')
    x_no_of_extra_knives_grid = fields.One2many('extra.knives.sub','x_extraknives_m','Extra Knives',copy=True,required=True)

    # @api.constrains('x_no_of_extra_knives_grid')
    # def _check_number(self):
    #     for rec in self:
    #         if rec.x_no_of_extra_knives_grid.x_extra_knives_sub and not re.match(r'^[0-9]+$', rec.x_no_of_extra_knives_grid.x_extra_knives_sub):
    #             raise ValidationError(_('Extra Knives should only contains numbers.'))


class ExtraKnivesSub(models.Model):
    _name = 'extra.knives.sub'
    _description = 'Extra Knives Sub'

    x_extra_knives_sub = fields.Integer('Number of Knives',required=True)
    x_upcharge_sub = fields.Float('Up-Charge',digits='EF Price')
    x_extraknives_m = fields.Many2one('extra.knives')

    # @api.constrains('x_extra_knives_sub')
    # def _check_number(self):
    #     for rec in self:
    #         if rec.x_extra_knives_sub and not re.match(r'^[0-9]+$', rec.x_extra_knives_sub):
    #             raise ValidationError(_('Extra Knives should only contains numbers.'))