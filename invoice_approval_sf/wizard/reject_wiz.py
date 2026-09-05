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

from odoo import api, models, fields, _


class InvRejection(models.TransientModel):
    _name = 'invoice.rejection'
    _description = 'Invoice Approval Rejection'

    move_id = fields.Many2one('account.move', default=lambda self: self.env.context.get('active_id'))
    reject_reason = fields.Text(required=True)

    def button_inv_reject(self):
        self.move_id.state = 'reject'
        message_body = _("Invoice is Rejected By %(user)s.", user=(self.env.user.name))
        self.move_id.message_post(body=message_body)