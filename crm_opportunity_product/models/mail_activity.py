# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, tools, _
from odoo.exceptions import UserError



class MailActivity(models.Model):
    _inherit = "mail.activity"

    def schedule_and_send_activity_email(self):
        """Send an email to the assigned user with activity details."""
        self.ensure_one()

        if not self.user_id or not self.user_id.email:
            raise UserError(_("No assigned user or email missing!"))

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        record_url = f"{base_url}/web#id={self.res_id}&model={self.res_model}&view_type=form"

        email_from = self.env.user.email_formatted or self.env.company.email_formatted
        if not email_from:
            raise UserError(_("No sender email address configured!"))

        subject = f"Activity Reminder: {self.activity_type_id.name}"
        body = f"""
        <p>Hello {self.user_id.name},</p>
        <br></br>
        <p>Here are your activity details:</p>
        <ul>
            <li><strong>Activity Type:</strong> {self.activity_type_id.name}</li>
            <li><strong>Summary:</strong> {self.summary or 'N/A'}</li>
            <li><strong>Note:</strong> {self.note or 'N/A'}</li>
            <li><strong>Due Date:</strong> {self.date_deadline}</li>
        </ul>
        <p>You can review it here: <a href="{record_url}">Open Record</a></p>
        <br></br>
        <p>Regards,<br/>{self.env.user.name}</p>
        """

        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_to': self.user_id.email_formatted,
            'email_from': email_from,
            'model': 'mail.activity',
            'res_id': self.id,
            'reply_to': email_from,
        }

        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Email sent successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
