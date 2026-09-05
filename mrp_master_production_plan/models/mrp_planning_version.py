# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date, datetime


class PlanningVersion (models.Model):
    _name = "mrp.planning.version"
    _description = "Planning Version"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date_start DESC"

    STATE_SELECTION = [
        ("open", _("Open")),
        ("closed", _("Closed")),
        ("cancel", _("Cancelled"))]


    name = fields.Char('Planning Version', required=True, tracking=True)
    active = fields.Boolean('Active', default=True, tracking=True)
    state = fields.Selection(STATE_SELECTION, 'State', index=True, required=True, copy=False, default='open', readonly=True, tracking=True)
    date_start = fields.Datetime('Start Date', required=True, tracking=True, default=datetime.strptime('%s-01-01' % (datetime.now().year+1),'%Y-%m-%d'))
    date_end = fields.Datetime("End Date", required=True, tracking=True, default=datetime.strptime('%s-12-31' % (datetime.now().year+1),'%Y-%m-%d'))
    notes = fields.Text('Notes')
    user_id = fields.Many2one('res.users', 'Planning Responsible', required=True, index=True, tracking=True, default=lambda self: self.env.user, check_company=True)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company.id)
    currency_id = fields.Many2one('res.currency', 'Currency', default=lambda self: self.env.user.company_id.currency_id.id)
    doc_count = fields.Integer("Number of attached documents", compute='_compute_attached_docs_count')
    pir_ids = fields.One2many('mrp.independent.requirements', 'origin', 'Planned Indipendent Requirements')
    pir_count = fields.Integer('PIRs Count', compute='_compute_pir_ids', store=True)
    pirs_revenues = fields.Float('PIRs Estimated Revenues', digits='Product Price', compute='calculate_pirs_amounts', store=True)
    pirs_costs = fields.Float('PIRs Estimated Costs', digits='Product Price', compute='calculate_pirs_amounts', store=True)


    def button_close(self):
        for record in self:
            record.state = 'closed'
        return True

    def button_open(self):
        for record in self:
            record.state = 'open'
        return True

    def button_cancel(self):
        for record in self:
            record.state = 'cancel'
        return True

    def button_reset(self):
        for record in self:
            record.state = 'open'
        return True

    @api.depends('pir_ids')
    def _compute_pir_ids(self):
        for version in self:
            version.pir_count = len(version.pir_ids)
        return True

    def action_view_pirs(self):
        action = self.env.ref('mrp_master_production_plan.mrp_pir_action').read()[0]
        pirs = self.env['mrp.independent.requirements'].search([('origin', '=', self.id)])
        if len(pirs) > 1:
            action['domain'] = "[('id', 'in', " + str(self.pir_ids.ids) + ")]"
        return action

    @api.depends('pir_ids', 'pir_ids.product_qty')
    def calculate_pirs_amounts(self):
        pirsrevenues = 0.0
        pirscosts = 0.0
        for version in self:
            for pir in version.pir_ids:
                pirsrevenues += pir.product_id.product_tmpl_id.list_price * pir.product_qty
                pirscosts += pir.product_id.standard_price * pir.product_qty
            version.pirs_revenues = pirsrevenues
            version.pirs_costs = pirscosts
        return True

    def unlink(self):
        for version in self:
            if version.pir_count > 0:
                raise UserError(_('linked PIRs still active, please delete them before'))
            else:
                super().unlink()
        return True

    @api.constrains('date_start','date_end')
    def _check_dates(self):
        if self.date_start >= self.date_end:
            raise UserError(_('Please check validity dates!'))
        return True

    def _compute_attached_docs_count(self):
        attachment = self.env['ir.attachment']
        for version in self:
            version.doc_count = attachment.search_count(['&',('res_model', '=', 'mrp.planning.version'), ('res_id', '=', version.id)])

    def attachment_tree_view(self):
        self.ensure_one()
        domain = ['&', ('res_model', '=', 'mrp.planning.version'), ('res_id', 'in', self.ids)]
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'ir.attachment',
            'type': 'ir.actions.act_window',
            'view_id': False,
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % (self._name, self.id)
        }