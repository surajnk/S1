from odoo import fields, models
from odoo.exceptions import UserError


class MrpWoPackagingWizard(models.TransientModel):
    _name = 'mrp.wo.packaging.wizard'
    _description = 'Work Order Packaging Report Wizard'

    date = fields.Date(
        string='Ship/Delivery Date',
        required=True,
        default=fields.Date.context_today,
        help="Manufacturing Orders whose Requested Date (x_so_delivery_date) "
             "matches this date will be included in the report.",
    )

    def _get_productions(self):
        self.ensure_one()
        return self.env['mrp.production'].search([
            ('x_so_delivery_date', '=', self.date),
            ('state', 'in', ('confirmed', 'progress')),
        ], order='name')

    def action_print_report(self):
        """Entry point triggered by the wizard's Print/Confirm button."""
        self.ensure_one()
        if not self._get_productions():
            raise UserError(
                "No confirmed or in-progress Manufacturing Orders were "
                "found with a Ship/Delivery Date of %s."
                % (self.date.strftime('%m/%d/%Y'))
            )
        return self.env.ref(
            'mrp_wo_packaging_report.action_report_mrp_wo_packaging'
        ).report_action(self)
