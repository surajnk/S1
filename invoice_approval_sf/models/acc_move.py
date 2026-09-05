# -*- coding: utf-8 -*-
##############################################################################
#
#    Shinefy Technologies Pvt. Ltd.
#    Copyright (C) 2022 Shinefy Technologies.
#    Author: Shinefy Technologies
#    
#    For Module Support : shinefytech@gmail.com  or Skype : shinefytech@gmail.com
#
##############################################################################

from odoo import api, fields, models, modules, _
from odoo.http import request
from ast import literal_eval
from odoo.exceptions import UserError

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    time_id = fields.Integer(string='MRP Time ID')


class AccountMove(models.Model):
    _inherit = 'account.move'

    state = fields.Selection(selection_add=[('to_approve', 'Waiting For Approval'),('approved', 'Approved'),('posted', 'Posted'),('reject', 'Rejected')], 
        ondelete={
            'to_approve': 'cascade',
            'approved': 'cascade',
            'posted': 'cascade',
            'reject': 'cascade'
        },)
    inv_appr_ids = fields.Many2many('res.users', string="Bill Approvers")
    is_user_approver = fields.Boolean(string="Is Approver?", compute="_check_approver")
    skip_approval = fields.Boolean(string="Skip Approval", copy=False)
    approver_id = fields.Many2one('res.users', string="Assigned Approver")
    time_id = fields.Integer(string='MRP Time ID')

    def get_approvers(self):
        app_from_setting = self.env['ir.config_parameter'].sudo().get_param('invoice_approval_sf.inv_appr_ids', self.inv_appr_ids) or False
        return app_from_setting

    def button_send_inv_app(self):
        if not self.skip_approval:
            self.state = 'to_approve'
            approver = self.approver_id
            
            if approver:
                inv_app_activity = self.env['mail.activity'].create({
                    'summary': 'Bill is sent for approval, For vendor %s please approve.' % (self.partner_id.name),
                    'activity_type_id': 1,
                    'res_id': self.id,
                    'user_id': approver.id,
                    'res_model_id': self.env.ref('invoice_approval_sf.model_account_move').id,
                })
            else:
                raise UserError("Please select an approver.")

    def button_inv_approve(self):
        for rec in self:
            if self._uid == rec.approver_id.id:
                self.state = 'approved'
                message_body = _("Bill is Approved By %(user)s.", user=(self.env.user.name))
                self.message_post(body=message_body)
            else:
                raise UserError("You cannot approve this Bill.")

    @api.depends('inv_appr_ids')
    def _check_approver(self):
        for rec in self:
            if self._uid in self.inv_appr_ids.ids:
                self.is_user_approver = True
            else:
                self.is_user_approver = False

    def button_reject(self):
        return {
            'name': 'Rejected Bill',
            'res_model': 'invoice.rejection',
            'view_mode': 'form',
            'context': {
                'active_model': 'account.move',
                'active_ids': self.ids,
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }

    # @api.model
    # def create(self, vals):
    #     if vals.get('skip_approval'):
    #         vals.pop('inv_appr_ids', None)  # Remove inv_appr_ids if skip_approval is True
    #     else:
    #         approver_id = vals.get('approver_id')
    #         if approver_id:
    #             vals['inv_appr_ids'] = [(4, approver_id)]  # Assign the selected approver

    #     res = super(AccountMove, self).create(vals)
    #     return res

    @api.model
    def create(self, vals):
        move_type = vals.get('move_type') or self.env.context.get('default_move_type')
        if move_type == 'out_invoice':
            vals['skip_approval'] = True
        if vals.get('skip_approval'):
            vals['state'] = 'approved'  # If skipping approval, set state to draft
        else:
            approver_id = vals.get('approver_id')
            if approver_id:
                vals['inv_appr_ids'] = [(4, approver_id)]  # Assign the selected approver
            else:
                vals['state'] = 'draft'  # Set to draft state if no approver is selected

        return super(AccountMove, self).create(vals)

    def write(self, vals):
        # If skip_approval is not coming in vals (common on normal save),
        # but record already has skip_approval=True and is currently in draft,
        # then on any edit/save we must push it back to approved.
        if 'skip_approval' not in vals:
            # allow pure "reset to draft" write: {'state': 'draft'}
            only_draft_reset = (set(vals.keys()) == {'state'} and vals.get('state') == 'draft')

            if not only_draft_reset:
                for move in self:
                    if move.skip_approval and move.state == 'draft':
                        vals = dict(vals)  # avoid mutating original dict reference
                        vals['state'] = 'approved'
                        break  # one change to vals is enough for this write call

        if 'skip_approval' in vals:
            if vals['skip_approval']:
                # If skip_approval is set to True, change state to 'approved'
                vals['state'] = 'approved'
                vals.pop('inv_appr_ids', None)  # Remove approvers if skipping approval
            else:
                # If skip_approval is set to False, ensure appropriate approval workflow
                approver_id = vals.get('approver_id', self.approver_id.id)
                if approver_id:
                    vals['inv_appr_ids'] = [(4, approver_id)]
                    vals['state'] = 'to_approve'  # Set to waiting for approval if approver is selected
                else:
                    vals['state'] = 'draft'  # Set to draft if no approver is selected

        return super(AccountMove, self).write(vals)

    
    # def write(self, vals):
    #     if 'skip_approval' in vals:
    #         if vals['skip_approval']:
    #             # If skip_approval is set to True, change state to 'approved'
    #             vals['state'] = 'approved'
    #             vals.pop('inv_appr_ids', None)  # Remove approvers if skipping approval
    #         else:
    #             # If skip_approval is set to False, ensure appropriate approval workflow
    #             approver_id = vals.get('approver_id', self.approver_id.id)
    #             if approver_id:
    #                 vals['inv_appr_ids'] = [(4, approver_id)]
    #                 vals['state'] = 'to_approve'  # Set to waiting for approval if approver is selected
    #             else:
    #                 vals['state'] = 'draft'  # Set to draft if no approver is selected

    #     return super(AccountMove, self).write(vals)


    # @api.model
    # def create(self, vals):
    #     res = super(AccountMove, self).create(vals)
    #     app = self.get_approvers()
    #     appr = app.replace("[", "").replace("]", "")
    #     if appr:
    #         my_list = appr.split(", ")
    #         res.write({"inv_appr_ids": [(6, 0, my_list)]})
    #     return res

    # def copy(self, default=None):
    #     if default is None:
    #         default = {}
    #     # Call the superclass method to perform the copy
    #     new_record = super(AccountMove, self).copy(default)
        
    #     # Retrieve the list of approvers
    #     app = self.get_approvers()
    #     appr = app.replace("[", "").replace("]", "")
        
    #     if appr:
    #         my_list = appr.split(", ")
    #         # Update the 'inv_appr_ids' field of the newly copied record
    #         new_record.write({"inv_appr_ids": [(6, 0, my_list)]})
        
    #     return new_record
