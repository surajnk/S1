# Copyright 2018 Open Source Integrators (http://www.opensourceintegrators.com)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    invoice_id = fields.Many2one(comodel_name="account.move", string="Invoice")
    discount_amt = fields.Monetary(store=True)
    invoice_ids = fields.Many2many(comodel_name="account.move", string="Invoice")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        active_id = self.env.context.get("active_ids", [])
        if len(active_id) == 1:
            record = self.env["account.move"].browse(active_id)
            res.update({"invoice_id": record.id, "discount_amt": record.discount_amt})
        else:
            invoices = self.env["account.move"].browse(active_id)
            total_discount_amt = sum(invoice.discount_amt for invoice in invoices)
            res.update({
                "invoice_ids": [(6, 0, invoices.ids)],  # Update with all invoice IDs
                "discount_amt": total_discount_amt
            })
        return res

    @api.onchange("amount")
    def onchange_payment_amount(self):
        active_id = self.env.context.get("active_ids", [])
        invoices = self.env["account.move"].browse(active_id)
        wizard_payment_difference = 0
        total = 0
        payment_difference = self.payment_difference
        for invoice_id in active_id:
            invoice = self.env["account.move"].browse(invoice_id)
            if (
                    invoice.invoice_payment_term_id
                    and invoice.invoice_payment_term_id.is_discount
                    and invoice.invoice_payment_term_id.line_ids
            ):

                self.payment_difference_handling = "open"
                self.writeoff_account_id = False
                self.writeoff_label = False

                for line in invoice.invoice_payment_term_id.line_ids:
                    # Check payment date discount validation
                    invoice_date = fields.Date.from_string(invoice.invoice_date)
                    till_discount_date = invoice_date + relativedelta(
                        days=line.discount_days
                    )
                    payment_date = fields.Date.from_string(self.payment_date)
                    discount_amt = invoice.discount_amt

                    if line.is_allow_give_discount:
                        discount_account = (
                            line.discount_income_account_id
                            if invoice.is_purchase_document()
                            else line.discount_expense_account_id
                        )
                        # changing payment date
                        if not payment_difference and discount_amt:

                            wizard_payment_difference += discount_amt
                            self.payment_difference_handling = "reconcile"
                            self.writeoff_account_id = discount_account.id
                            self.writeoff_label = "Payment Discount"
                        # customer is paying more
                        elif abs(payment_difference) < discount_amt:

                            wizard_payment_difference += abs(payment_difference)
                            self.payment_difference_handling = "reconcile"
                            self.writeoff_account_id = discount_account.id
                            self.writeoff_label = "Payment Discount"
                        # ocustomer paying more than discount_amt
                        elif abs(payment_difference) > discount_amt:

                            wizard_payment_difference += abs(payment_difference)
                            self.payment_difference_handling = "open"
                            self.writeoff_label = False
                        # customer paying more than discount_amt
                        elif abs(payment_difference) == discount_amt and discount_amt > 0:

                            wizard_payment_difference += abs(payment_difference)
                            self.payment_difference_handling = "reconcile"
                            self.writeoff_account_id = discount_account.id
                            self.writeoff_label = "Payment Discount"

                    else:

                        wizard_payment_difference += payment_difference

                    if not line.is_allow_give_discount:
                        if payment_date <= till_discount_date:
                            discount_account = (
                                line.discount_income_account_id
                                if invoice.is_purchase_document()
                                else line.discount_expense_account_id
                            )
                            # changing payment date
                            if not payment_difference and discount_amt:

                                wizard_payment_difference += discount_amt
                                self.payment_difference_handling = "reconcile"
                                self.writeoff_account_id = discount_account.id
                                self.writeoff_label = "Payment Discount"
                            # customer is paying more
                            elif abs(payment_difference) < discount_amt:

                                wizard_payment_difference += abs(payment_difference)
                                self.payment_difference_handling = "reconcile"
                                self.writeoff_account_id = discount_account.id
                                self.writeoff_label = "Payment Discount"
                            # ocustomer paying more than discount_amt
                            elif abs(payment_difference) > discount_amt:

                                wizard_payment_difference += abs(payment_difference)
                                self.payment_difference_handling = "open"
                                self.writeoff_label = False
                            # customer paying more than discount_amt
                            elif abs(payment_difference) == discount_amt and discount_amt > 0:

                                wizard_payment_difference += abs(payment_difference)
                                self.payment_difference_handling = "reconcile"
                                self.writeoff_account_id = discount_account.id
                                self.writeoff_label = "Payment Discount"

                        else:

                            wizard_payment_difference += payment_difference

        if wizard_payment_difference > 0:
            self.payment_difference = wizard_payment_difference
            self.amount = self.amount - abs(
                self.payment_difference
            )


    # def action_create_payments(self):
    #     payments = self._create_payments()
    #
    #     if self._context.get('dont_redirect_to_payments'):
    #         return True
    #
    #     action = {
    #         'name': _('Payments'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'account.payment',
    #         'context': {'create': False},
    #     }
    #     if len(payments) == 1:
    #         action.update({
    #             'view_mode': 'form',
    #             'res_id': payments.id,
    #         })
    #     else:
    #         action.update({
    #             'view_mode': 'tree,form',
    #             'domain': [('id', 'in', payments.ids)],
    #         })
    #     return action

    # def action_create_payments(self):
    #     active_ids = self.env.context.get("active_ids", [])
    #
    #     if not active_ids:
    #         raise UserError(_("No invoices or bills selected for payment."))
    #
    #     payments_created = self.env["account.payment"]
    #     for payment_wizard in self:
    #         for invoice_id in payment_wizard.invoice_ids.ids:
    #             invoice = self.env["account.move"].browse(invoice_id)
    #             payment_vals = payment_wizard._prepare_payment_values(invoice)
    #             payment = self.env["account.payment"].create(payment_vals)
    #             payment.post()
    #             payments_created += payment
    #
    #             # Update invoice fields if payment difference is reconciled
    #             if payment.payment_difference_handling == "reconcile":
    #                 invoice.write({
    #                     "discount_taken": abs(payment.payment_difference),
    #                     "discount_amt": 0,
    #                 })
    #
    #     return {
    #         "type": "ir.actions.act_window_close",
    #     }

    # @api.onchange("amount", "payment_difference", "payment_date")
    # def onchange_payment_amount(self):
    #     if (
    #             self.invoice_id
    #             and self.invoice_id.invoice_payment_term_id
    #             and self.invoice_id.invoice_payment_term_id.is_discount
    #             and self.invoice_id.invoice_payment_term_id.line_ids
    #     ):
    #
    #         self.payment_difference_handling = "open"
    #         self.writeoff_account_id = False
    #         self.writeoff_label = False
    #
    #         for line in self.invoice_id.invoice_payment_term_id.line_ids:
    #             # Check payment date discount validation
    #             invoice_date = fields.Date.from_string(self.invoice_id.invoice_date)
    #             till_discount_date = invoice_date + relativedelta(
    #                 days=line.discount_days
    #             )
    #             payment_date = fields.Date.from_string(self.payment_date)
    #             discount_amt = self.invoice_id.discount_amt
    #
    #             payment_difference = self.payment_difference
    #             self.payment_difference = 0.0
    #
    #             if line.is_allow_give_discount:
    #                 discount_account = (
    #                     line.discount_income_account_id
    #                     if self.invoice_id.is_purchase_document()
    #                     else line.discount_expense_account_id
    #                 )
    #                 # changing payment date
    #                 if not payment_difference and discount_amt:
    #
    #                     self.payment_difference = discount_amt
    #                     self.payment_difference_handling = "reconcile"
    #                     self.writeoff_account_id = discount_account.id
    #                     self.writeoff_label = "Payment Discount"
    #                 # customer is paying more
    #                 elif abs(payment_difference) < discount_amt:
    #
    #                     self.payment_difference = abs(payment_difference)
    #                     self.payment_difference_handling = "reconcile"
    #                     self.writeoff_account_id = discount_account.id
    #                     self.writeoff_label = "Payment Discount"
    #                 # ocustomer paying more than discount_amt
    #                 elif abs(payment_difference) > discount_amt:
    #
    #                     self.payment_difference = abs(payment_difference)
    #                     self.payment_difference_handling = "open"
    #                     self.writeoff_label = False
    #                 # customer paying more than discount_amt
    #                 elif abs(payment_difference) == discount_amt and discount_amt > 0:
    #
    #                     self.payment_difference = abs(payment_difference)
    #                     self.payment_difference_handling = "reconcile"
    #                     self.writeoff_account_id = discount_account.id
    #                     self.writeoff_label = "Payment Discount"
    #
    #             else:
    #
    #                 self.payment_difference = payment_difference
    #
    #             if not line.is_allow_give_discount:
    #                 if payment_date <= till_discount_date:
    #                     discount_account = (
    #                         line.discount_income_account_id
    #                         if self.invoice_id.is_purchase_document()
    #                         else line.discount_expense_account_id
    #                     )
    #                     # changing payment date
    #                     if not payment_difference and discount_amt:
    #
    #                         self.payment_difference = discount_amt
    #                         self.payment_difference_handling = "reconcile"
    #                         self.writeoff_account_id = discount_account.id
    #                         self.writeoff_label = "Payment Discount"
    #                     # customer is paying more
    #                     elif abs(payment_difference) < discount_amt:
    #
    #                         self.payment_difference = abs(payment_difference)
    #                         self.payment_difference_handling = "reconcile"
    #                         self.writeoff_account_id = discount_account.id
    #                         self.writeoff_label = "Payment Discount"
    #                     # ocustomer paying more than discount_amt
    #                     elif abs(payment_difference) > discount_amt:
    #
    #                         self.payment_difference = abs(payment_difference)
    #                         self.payment_difference_handling = "open"
    #                         self.writeoff_label = False
    #                     # customer paying more than discount_amt
    #                     elif abs(payment_difference) == discount_amt and discount_amt > 0:
    #
    #                         self.payment_difference = abs(payment_difference)
    #                         self.payment_difference_handling = "reconcile"
    #                         self.writeoff_account_id = discount_account.id
    #                         self.writeoff_label = "Payment Discount"
    #
    #                 else:
    #
    #                     self.payment_difference = payment_difference
    #
    #             self.amount = self.invoice_id.amount_residual - abs(
    #                 self.payment_difference
    #             )

    # def action_create_payments(self):
    #     active_id = self.env.context.get("active_ids", [])
    #
    #     # if (not isinstance(active_id, int)) and len(active_id) != 1:
    #     #     # For multiple invoices, there is account.register.payments wizard
    #     #     raise UserError(
    #     #         _(
    #     #             "This method should only be called to process a "
    #     #             "single invoice's payment."
    #     #         )
    #     #     )
    #     res = super().action_create_payments()
    #     for payment in self:
    #         if payment.payment_difference_handling == "reconcile":
    #             payment.invoice_id.write(
    #                 {
    #                     "discount_taken": abs(payment.payment_difference),
    #                     "discount_amt": 0,
    #                 }
    #             )
    #     return res
