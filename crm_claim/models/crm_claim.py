# Copyright 2015-2017 Odoo S.A.
# Copyright 2017 Tecnativa - Vicent Cubells
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import _, api, fields, models
from odoo.tools import html2plaintext
import logging
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

APPLICABLE_MODELS = [
    "account.invoice",
    "event.registration",
    "hr.applicant",
    "res.partner",
    "product.product",
    "purchase.order",
    "purchase.order.line",
    "sale.order",
    "sale.order.line",
]


class CrmClaim(models.Model):
    _name = "crm.claim"
    _description = "Complaint"
    _order = "priority,date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    @api.model
    def _get_default_stage_id(self):
        """ Gives default stage_id """
        team_id = self.env["crm.team"]._get_default_team_id()
        return self.env['crm.claim'].stage_find(team_id.id, [("sequence", "=", "1")])
 

    @api.model
    def _get_default_team(self):
        return self.env["crm.team"]._get_default_team_id()

    @api.model
    def _selection_model(self):
        return [
            (x, _(self.env[x]._description)) for x in APPLICABLE_MODELS if x in self.env
        ]

    name = fields.Char(string="Complaint Subject", required=True)
    active = fields.Boolean(default=True)
    description = fields.Text()
    resolution = fields.Text()
    create_date = fields.Datetime(string="Creation Date", readonly=True)
    write_date = fields.Datetime(string="Update Date", readonly=True)
    date_deadline = fields.Date(string="Deadline")
    date_closed = fields.Datetime(string="Closed", readonly=True)
    date = fields.Datetime(string="Complaint Date", index=True, default=fields.Datetime.now)
    model_ref_id = fields.Reference(
        selection="_selection_model", string="Model Reference"
    )
    categ_id = fields.Many2one(comodel_name="crm.claim.category", string="Category")
    priority = fields.Selection(
        selection=[("0", "Low"), ("1", "Normal"), ("2", "High")], default="1"
    )
    type_action = fields.Selection(
        selection=[
            ("correction", "Corrective Action"),
            ("prevention", "Preventive Action"),
        ],
        string="Action Type",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Created by",
        tracking=True,
        default=lambda self: self.env.user,
    )
    user_fault = fields.Char(string="Trouble Responsible")
    team_id = fields.Many2one(
        comodel_name="crm.team",
        string="Sales Team",
        index=True,
        default=_get_default_team,
        help="Responsible sales team. Define Responsible user and Email "
             "account for mail gateway.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one(comodel_name="res.partner", string="Partner")
    email_cc = fields.Text(
        string="Watchers Emails",
        help="These email addresses will be added to the CC field of all "
             "inbound and outbound emails for this record before being sent. "
             "Separate multiple email addresses with a comma",
    )
    email_from = fields.Char(
        string="Email", help="Destination email for email gateway."
    )
    partner_phone = fields.Char(string="Phone")
    customer_po_number = fields.Char(string="Customer PO")
    sale_order_ids = fields.Many2many(
        'sale.order',
        string='Sale Orders',
        compute='_compute_related_orders',
        readonly=True,
    )
    mrp_production_ids = fields.Many2many(
        'mrp.production',
        string='Manufacturing Orders',
        compute='_compute_related_orders',
        readonly=True,
    )
    stage_id = fields.Many2one(
        comodel_name="crm.claim.stage",
        string="Stage",
        tracking=3,
        default=_get_default_stage_id,
        domain="['|', ('team_ids', '=', team_id), ('case_default', '=', True)]",
    )
    status = fields.Selection(
        selection=[
            ('new', 'New'),
            ('in_progress', 'In Progress'),
            ('settled', 'Settled'),
            ('rejected', 'Rejected')
        ],
        string='Status',
        default='new'
    )
    cause = fields.Text(string="Root Cause")
    type = fields.Selection([('customer_invoice', 'Customer Invoice'), ('vendor_bills', 'Vendor Bills')], string="Type")
    invoice_id = fields.Many2one('account.move', string="Invoice", )
    credit_not_count = fields.Integer(string="Credit Note", compute="compute_credit_not")

    complaints_lines_option = fields.Selection([
        ('customer_invoices', 'Customer Invoice Lines'),
        ('purchase_bills', 'Vendor Bill Lines'),
        ('purch_bills', 'Vendor Bill'),
        ('cust_bills', 'Customer Invoice'),
        ('sale_orders', 'Sales Order'),
        ('manufacturing_order', 'Manufacturing Order')
    ], string='Option', required=True)

    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sale Order',
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        domain="[('order_id', '=', sale_order_id)]",
    )
    manufacturing_order_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
    )
    lots = fields.Char(string='Lots')


    invoice_line_complaint_ids = fields.One2many('account.move.line', 'wizard_complaints_id', string='Invoice Lines')

    invoice_line_ids = fields.Many2many(
        'account.move.line', 
        string='Invoice Lines',
        domain="[('move_id.move_type', '=', move_type_filter)]"
    )

    invoices_ids = fields.Many2many(
        'account.move', 
        string='Invoice/Bills',
        domain="[('move_type', '=', move_type_filter)]"
    )

    move_type_filter = fields.Selection(
        selection=[("out_invoice", "Customer Invoice"), ("in_invoice", "Vendor Bill")],
        compute="_compute_move_type_filter",
        store=True
    )

    group_comp_user_id = fields.Many2one(
        'res.users',
        string='Approver',
        domain=lambda self: [('groups_id', 'in', self.env.ref('crm_claim.group_comp').id)]
    )

    def action_submit_complaint(self):
        for record in self:
            if not record.group_comp_user_id:
                raise UserError(_("Please select an approver before submitting the complaint."))


            record.status = 'in_progress'

            # Assign the complaint to the selected approver
            record.user_id = record.group_comp_user_id
            if record.sale_order_id:
                record.sale_order_id.state = 'complained'
            if record.manufacturing_order_id:
                record.manufacturing_order_id.state = 'complained'
            if record.invoice_line_ids or record.invoices_ids:
                invoices = record.invoice_line_ids.mapped('move_id') | record.invoices_ids
                invoices.write({'is_complained': True})

            # Send a notification to the approver
            record.message_post(
                body=_("The complaint has been submitted for your approval."),
                partner_ids=[record.group_comp_user_id.partner_id.id]
            )

            # Create an activity for the approver
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=record.group_comp_user_id.id,
                note=_("Please review and approve the submitted complaint.")
            )

    def action_approve_complaint(self):
        for record in self:
            if not record.resolution:
                raise UserError(_("Please update Resolutions under Follow Up space"))
            record.status = 'settled'
            # Send a notification to the creator of the complaint
            record.message_post(
                body=_("Your complaint '%s' has been approved.") % record.name,
                partner_ids=[record.create_uid.partner_id.id]
            )

            # Create an activity for the creator
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=record.create_uid.id,
                note=_("Your complaint '%s' has been approved. Please check the resolution.") % record.name
            )

    def action_reject_complaint(self):
        for record in self:
            if not record.resolution:
                raise UserError(_("Please update Resolutions under Follow Up space"))
            record.status = 'rejected'
            record.message_post(
                body=_("Your complaint '%s' has been rejected.") % record.name,
                partner_ids=[record.create_uid.partner_id.id]
            )

            # Create an activity for the creator
            record.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=record.create_uid.id,
                note=_("Your complaint '%s' has been rejected. Please check the resolution.") % record.name
            )

    @api.depends("complaints_lines_option")
    def _compute_move_type_filter(self):
        for record in self:
            if record.complaints_lines_option == "customer_invoices":
                record.move_type_filter = "out_invoice"
            elif record.complaints_lines_option == "purchase_bills":
                record.move_type_filter = "in_invoice"
            elif record.complaints_lines_option == "purch_bills":
                record.move_type_filter = "in_invoice"
            elif record.complaints_lines_option == "cust_bills":
                record.move_type_filter = "out_invoice"
            elif record.complaints_lines_option in ("sale_orders", "manufacturing_order"):
                record.move_type_filter = False
            else:
                record.move_type_filter = False

    @api.onchange('complaints_lines_option')
    def _onchange_complaints_lines_option(self):
        domain = []
        invoice_domain = []
        if self.complaints_lines_option == 'customer_invoices':
            domain = [('move_id.move_type', '=', 'out_invoice')]
            invoice_domain = [('move_type', '=', 'out_invoice')]
        elif self.complaints_lines_option == 'purchase_bills':
            domain = [('move_id.move_type', '=', 'in_invoice')]
            invoice_domain = [('move_type', '=', 'in_invoice')]
        elif self.complaints_lines_option == 'purch_bills':
            invoice_domain = [('move_type', '=', 'in_invoice')]
        elif self.complaints_lines_option == 'cust_bills':
            invoice_domain = [('move_type', '=', 'out_invoice')]
        elif self.complaints_lines_option in ('sale_orders', 'manufacturing_order'):
            domain = []
            invoice_domain = []

        _logger.info(f"Domain for invoice_line_ids: {domain}")
        _logger.info(f"Domain for invoices_ids: {invoice_domain}")
        return {
            'domain': {
                'invoice_line_ids': domain,
                'invoices_ids': invoice_domain
            }
        }
    
    
    
    # @api.onchange('complaints_lines_option')
    # def _onchange_option(self):
    #     if self.complaints_lines_option == 'customer_invoices':
    #         return {'domain': {'invoice_line_complaint_ids': [('move_id.move_type', '=', 'out_invoice')]}}
    #     elif self.complaints_lines_option == 'purchase_bills':
    #         return {'domain': {'invoice_line_complaint_ids': [('move_id.move_type', '=', 'in_invoice')]}}

    # @api.onchange('complaints_lines_option')
    # def _onchange_complaints_lines_option(self):
    #     domain = []
    #     if self.complaints_lines_option == 'customer_invoices':
    #         domain = [('move_id.move_type', '=', 'out_invoice')]
    #     elif self.complaints_lines_option == 'purchase_bills':
    #         domain = [('move_id.move_type', '=', 'in_invoice')]
    #     _logger.info(f"Domain for invoice_line_ids: {domain}")
    #     return {'domain': {'invoice_line_ids': domain}}
    
    def action_crm_complaints_wizard(self):
        """Ensure record is saved before opening the wizard."""
        self.ensure_one()  # Ensures we work with a single record

        if not self.id:
            self = self.create(self._convert_to_write(self._cache))  # Force save
            self.flush()  # Ensure it's written to DB

        if not self.id:
            raise UserError("Error: Could not generate a Complaint ID.")
        return {
            "name": "Select Invoice Lines",
            "type": "ir.actions.act_window",
            "res_model": "crm.complaints.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("crm_claim.view_crm_complaints_wizard_form").id,
            "target": "new",
            "context": {
                "default_complaint_id": self.id,  # Now it should be saved
                "default_complaints_lines_option": self.complaints_lines_option,
                "default_move_type_filter": "out_invoice" if self.complaints_lines_option == "customer_invoices" else "in_invoice",
            },
        }


    # def action_crm_complaints_wizard(self):
    #     """Open wizard to select invoice lines based on complaint type."""
    #     return {
    #         "name": "Select Invoice Lines",
    #         "type": "ir.actions.act_window",
    #         "res_model": "crm.complaints.wizard",
    #         "view_mode": "form",
    #         "view_id": self.env.ref("crm_claim.view_crm_complaints_wizard_form").id,
    #         "target": "new",
    #         "context": {
    #             "default_complaint_id": self.id,
    #             "default_complaints_lines_option": self.complaints_lines_option,
    #             "default_move_type_filter": "out_invoice" if self.complaints_lines_option == "customer_invoices" else "in_invoice",
    #         },
    #     }


    def create_invoice_action(self):
        # Get the invoice IDs from the selected invoice lines
        invoice_ids = (self.invoice_line_ids.mapped('move_id') | self.invoices_ids).ids
        
        # Retrieve the action for opening the list view of customer invoices
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        
        # Set the domain to filter the invoices based on the selected invoice lines
        action['domain'] = [('id', 'in', invoice_ids)]
        
        # Set the context for the action
        context = {
            'default_move_type': 'out_invoice',
        }
        action['context'] = context
        
        return action

    def action_credit_not(self):
        invoice_ids = self.env['account.move'].search(
            [('name', '=', "R" + self.invoice_id.name), ('move_type', '=', 'out_refund')]).ids
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        action['domain'] = [('id', 'in', invoice_ids)]
        context = {
            'default_move_type': 'out_invoice',
        }
        action['context'] = context
        return action


    def compute_credit_not(self):
        for rec in self:
            if rec.invoice_id:
                name = "R" + rec.invoice_id.name
                credit = self.env['account.move'].search([('name', '=', name), ('move_type', '=', 'out_refund')])
                if credit:
                    rec.credit_not_count = len(credit)
                else:
                    rec.credit_not_count = 0
            else:
                rec.credit_not_count = 0

    @api.depends('customer_po_number')
    def _compute_related_orders(self):
        for rec in self:
            if rec.customer_po_number:
                sale_orders = self.env['sale.order'].search([('client_order_ref', '=', rec.customer_po_number)])
                rec.sale_order_ids = sale_orders
                productions = sale_orders.mapped('procurement_group_id.stock_move_ids.created_production_id.procurement_group_id.mrp_production_ids')
                rec.mrp_production_ids = productions
            else:
                rec.sale_order_ids = False
                rec.mrp_production_ids = False

    def stage_find(self, team_id, domain=None, order="sequence"):
        """Override of the base.stage method
        Parameter of the stage search taken from the lead:
        - team_id: if set, stages must belong to this team or
          be a default case
        """
        if domain is None:  # pragma: no cover
            domain = []
        # collect all team_ids
        team_ids = []
        if team_id:
            team_ids.append(team_id)
        team_ids.extend(self.mapped("team_id").ids)
        search_domain = []
        if team_ids:
            search_domain += ["|"] * len(team_ids)
            for team_id in team_ids:
                search_domain.append(("team_ids", "=", team_id))
        search_domain.append(("case_default", "=", True))
        # AND with the domain in parameter
        search_domain += list(domain)
        # perform search, return the first found
        return (
            self.env["crm.claim.stage"].search(search_domain, order=order, limit=1).id
        )

    @api.onchange("partner_id")
    def onchange_partner_id(self):
        """This function returns value of partner address based on partner
        :param email: ignored
        """
        if self.partner_id:
            self.email_from = self.partner_id.email
            self.partner_phone = self.partner_id.phone

    @api.onchange("categ_id")
    def onchange_categ_id(self):
        if self.stage_id:
            self.team_id = self.categ_id.team_id

    @api.model
    def create(self, values):
        ctx = self.env.context.copy()
        if values.get("team_id") and not ctx.get("default_team_id"):
            ctx["default_team_id"] = values.get("team_id")
        return super(CrmClaim, self.with_context(context=ctx)).create(values)

    def copy(self, default=None):
        default = dict(
            default or {},
            stage_id=self._get_default_stage_id(),
            name=_("%s (copy)") % self.name,
        )
        return super(CrmClaim, self).copy(default)

    # -------------------------------------------------------
    # Mail gateway
    # -------------------------------------------------------
    @api.model
    def message_new(self, msg, custom_values=None):
        """Overrides mail_thread message_new that is called by the mailgateway
        through message_process.
        This override updates the document according to the email.
        """
        if custom_values is None:
            custom_values = {}
        desc = html2plaintext(msg.get("body")) if msg.get("body") else ""
        defaults = {
            "name": msg.get("subject") or _("No Subject"),
            "description": desc,
            "email_from": msg.get("from"),
            "email_cc": msg.get("cc"),
            "partner_id": msg.get("author_id", False),
        }
        if msg.get("priority"):
            defaults["priority"] = msg.get("priority")
        defaults.update(custom_values)
        return super(CrmClaim, self).message_new(msg, custom_values=defaults)

