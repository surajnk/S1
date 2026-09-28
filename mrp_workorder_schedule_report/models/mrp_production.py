from odoo import api, fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    trial = fields.Boolean(
        string='Trial',
        help='Marks this manufacturing order as a trial order. Trial orders get '
             'an auto-assigned trial number and are shown as "TRIAL" on the '
             'workorder schedule report instead of the usual part/customer info.',
    )
    trial_no = fields.Char(
        string='Trial No.',
        copy=False,
        readonly=True,
        help='Auto-assigned sequence number for trial orders (e.g. T02681).',
    )

    def _assign_trial_no(self):
        for production in self:
            if production.trial and not production.trial_no:
                production.trial_no = self.env['ir.sequence'].next_by_code(
                    'mrp.production.trial'
                )

    @api.model_create_multi
    def create(self, vals_list):
        productions = super().create(vals_list)
        productions._assign_trial_no()
        return productions

    def write(self, vals):
        res = super().write(vals)
        if vals.get('trial'):
            self._assign_trial_no()
        return res
