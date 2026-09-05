# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import Warning


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    
    @api.model
    def default_get(self,fields):
        res = super(SaleOrder, self).default_get(fields)
        branch_id = warehouse_id = False
        if self.env.user.branch_id:
            branch_id = self.env.user.branch_id.id
        if branch_id:
            branched_warehouse = self.env['stock.warehouse'].search([('branch_id','=',branch_id)])
            if branched_warehouse:
                warehouse_id = branched_warehouse.id
        else:
            warehouse_id = self._default_warehouse_id()
            warehouse_id = warehouse_id.id

        res.update({
            'branch_id' : branch_id,
            'warehouse_id' : warehouse_id
            })

        return res

    branch_id = fields.Many2one('res.branch', change_default=True,string="Branch")

    
    def _prepare_invoice(self):
        res = super(SaleOrder, self)._prepare_invoice()
        res['branch_id'] = self.branch_id.id
        return res


    @api.onchange('branch_id')
    def _onchange_branch_id(self):
        selected_brach = self.branch_id
        if selected_brach:
            user_id = self.env['res.users'].browse(self.env.uid)
            user_branch = user_id.sudo().branch_id
            if user_branch and user_branch.id != selected_brach.id:
                raise Warning("Please select active branch only. Other may create the Multi branch issue. \n\ne.g: If you wish to add other branch then Switch branch from the header and set that.")

    def action_quotation_send(self):
        self.ensure_one()
        action = super(SaleOrder, self).action_quotation_send()
        if action.get('context'):
            action['context'].update({
                'default_is_receive_parent_mail': True,
            })

        return action

class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'


    is_receive_parent_mail = fields.Boolean(string="Is Receive parent mail?", default=False)

    @api.onchange('template_id', 'model', 'res_id', 'is_receive_parent_mail')
    def onchange_receive_parent_mail(self):
        if self.model and self.res_id and self.is_receive_parent_mail:
            record = self.env[self.model].browse(self.res_id)
            if record.partner_id:
                sub_contacts = record.partner_id.child_ids.filtered(lambda c: c.receive_parent_mail)
                self.partner_ids |= sub_contacts

