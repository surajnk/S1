from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
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
        for order in self:
            claims = self.env['crm.claim'].search([
                ('sale_order_id', '=', order.id)
            ])
            order.crm_claim_ids = claims
            order.crm_claim_count = len(claims)

    def action_view_crm_claims(self):
        self.ensure_one()
        action = self.env.ref('crm_claim.crm_claim_category_claim0').read()[0]
        action['domain'] = [('id', 'in', self.crm_claim_ids.ids)]
        action['context'] = {'default_sale_order_id': self.id}
        return action
