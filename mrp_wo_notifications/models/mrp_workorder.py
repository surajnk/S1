# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models
from odoo.tools.float_utils import float_compare


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    under_produced = fields.Boolean(string='Under Produced', default=False)
    over_produced = fields.Boolean(string='Over Produced', default=False)
    allowances_acknowledged = fields.Boolean(
        string='Allowances acknowledged',
        default=False,
    )

    def button_finish(self):
        res = super().button_finish()
        self._update_production_deviation_flags()
        self._notify_underproduction_workorders()
        return res

    def _update_production_deviation_flags(self):
        for workorder in self:
            production = workorder.production_id
            if production:
                try:
                    under_pct = float(str(production.x_order_mrp_under or '0').replace('%', '').strip())
                except ValueError:
                    under_pct = 0.0
                try:
                    over_pct = float(str(production.x_order_mrp_over or '0').replace('%', '').strip())
                except ValueError:
                    over_pct = 0.0
            else:
                under_pct = 0.0
                over_pct = 0.0

            minimum_qty = max(workorder.qty_output_wo * (1 - under_pct / 100.0), 0.0)
            maximum_qty = max(workorder.qty_output_wo * (1 + over_pct / 100.0), 0.0)

            workorder.under_produced = workorder.total_produce_quantity < minimum_qty
            workorder.over_produced = workorder.total_produce_quantity > maximum_qty

    def action_acknowledge_allowances(self):
        self.write({'allowances_acknowledged': True})

    def _notify_underproduction_workorders(self):
        Mail = self.env['mail.mail'].sudo()
        author = self.env.user.partner_id.id if self.env.user.partner_id else False
        email_from = self.env.user.email or self.env.user.company_id.email or False
        now_dt = fields.Datetime.to_datetime(fields.Datetime.now())

        timeframe_map = {
            'last_week': relativedelta(weeks=1),
            'last_two_weeks': relativedelta(weeks=2),
            'last_month': relativedelta(months=1),
        }

        for workorder in self:
            company = workorder.company_id
            if not company.enable_wo_notifications:
                continue

            recipients = company.wo_notification_user_ids.filtered(lambda u: u.partner_id.email)
            if not recipients:
                continue

            delta = timeframe_map.get(company.wo_notification_timeframe or 'last_week')
            if delta:
                earliest_date = now_dt - delta
                workorder_create_dt = fields.Datetime.to_datetime(workorder.create_date) if workorder.create_date else False
                if workorder_create_dt and workorder_create_dt < earliest_date:
                    continue

            rounding = (
                workorder.product_uom_id.rounding
                if workorder.product_uom_id
                else workorder.production_id.product_uom_id.rounding
            )
            produced_qty = workorder.total_produce_quantity or 0.0
            planned_qty = workorder.qty_output_wo or 0.0
            if (
                float_compare(
                    produced_qty,
                    planned_qty,
                    precision_rounding=rounding or 0.01,
                )
                >= 0
            ):
                continue

            subject = _('Workorder %s produced less than planned') % (workorder.display_name or workorder.name)
            body = _(
                'The workorder %(wo)s produced %(produced)s %(uom)s which is below the planned quantity of %(planned)s %(uom)s.'
            ) % {
                'wo': workorder.display_name or workorder.name,
                'produced': produced_qty,
                'planned': planned_qty,
                'uom': workorder.product_uom_id.display_name
                if workorder.product_uom_id
                else workorder.production_id.product_uom_id.display_name,
            }

            body_html = '<p>%s</p>' % body
            if workorder.production_id:
                body_html += '<p>%s</p>' % (
                    _('Manufacturing Order: %s') % (workorder.production_id.display_name,)
                )

            mail_values = {
                'subject': subject,
                'body_html': body_html,
                'email_to': ','.join(recipient.partner_id.email for recipient in recipients),
                'author_id': author,
            }
            if email_from:
                mail_values['email_from'] = email_from
            Mail.create(mail_values).send()
