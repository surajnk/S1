from odoo import api, fields, models
import logging
_logger = logging.getLogger(__name__)


class CrmComplaintsWizard(models.TransientModel):
    _name = 'crm.complaints.wizard'
    _description = 'CRM Complaints Wizard'

    complaint_id = fields.Many2one("crm.claim", string="Complaint")
    
    complaints_lines_option = fields.Selection([
        ('customer_invoices', 'Customer Invoices'),
        ('purchase_bills', 'Purchase Bills')
    ], string="Option", required=True, default="customer_invoices")


    move_type_filter = fields.Selection(
        selection=[("out_invoice", "Customer Invoice"), ("in_invoice", "Vendor Bill")],
        compute="_compute_move_type_filter",
        store=True
    )


    invoice_line_ids = fields.Many2many(
        "account.move.line", 
        string="Invoice Lines",
        domain="[('move_id.move_type', '=', move_type_filter)]"
    )

    @api.onchange('complaints_lines_option')
    def _onchange_complaints_lines_option(self):
        domain = []
        if self.complaints_lines_option == 'customer_invoices':
            domain = [('move_id.move_type', '=', 'out_invoice')]
        elif self.complaints_lines_option == 'purchase_bills':
            domain = [('move_id.move_type', '=', 'in_invoice')]
        _logger.info(f"Domain for invoice_line_ids: {domain}")
        return {'domain': {'invoice_line_ids': domain}}
    
    @api.depends("complaints_lines_option")
    def _compute_move_type_filter(self):
        for record in self:
            if record.complaints_lines_option == "customer_invoices":
                record.move_type_filter = "out_invoice"
            elif record.complaints_lines_option == "purchase_bills":
                record.move_type_filter = "in_invoice"
            else:
                record.move_type_filter = False


    def action_apply(self):
        """Assign selected invoice lines to the complaint."""
        self.ensure_one()
        if self.invoice_line_ids:
            self.complaint_id.invoice_line_complaint_ids = [(6, 0, self.invoice_line_ids.ids)]
        return {"type": "ir.actions.act_window_close"}