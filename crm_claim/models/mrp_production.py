from odoo import fields, models, api


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('progress', 'In Progress'),
        ('to_close', 'To Close'),
        ('done', 'Done'),
        ('complained', 'Complained'),
        ('cancel', 'Cancelled')], string='State',
        compute='_compute_state', copy=False, index=True, readonly=True,
        store=True, tracking=True,
        help=" * Draft: The MO is not confirmed yet.\n"
             " * Confirmed: The MO is confirmed, the stock rules and the reordering of the components are trigerred.\n"
             " * In Progress: The production has started (on the MO or on the WO).\n"
             " * To Close: The production is done, the MO has to be closed.\n"
             " * Done: The MO is closed, the stock moves are posted. \n"
             " * Cancelled: The MO has been cancelled, can't be confirmed anymore.")

    crm_claim_ids = fields.Many2many(
        'crm.claim',
        string='Complaints',
        compute='_compute_crm_claims',
        readonly=True,
    )
    crm_claim_count = fields.Integer(
        string='Complaints',
        compute='_compute_crm_claims'
    )

    @api.depends('state')
    def _compute_crm_claims(self):
        for production in self:
            claims = self.env['crm.claim'].search([
                ('manufacturing_order_id', '=', production.id)
            ])
            production.crm_claim_ids = claims
            production.crm_claim_count = len(claims)

    def action_view_crm_claims(self):
        self.ensure_one()
        action = self.env.ref('crm_claim.crm_claim_category_claim0').read()[0]
        action['domain'] = [('id', 'in', self.crm_claim_ids.ids)]
        action['context'] = {'default_manufacturing_order_id': self.id}
        return action
