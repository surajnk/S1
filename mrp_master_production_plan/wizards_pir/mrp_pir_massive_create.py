# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpPirCreateWizard(models.TransientModel):
    _name = "mrp.pir.create.wizard"
    _description = "Planned Independent Requirements Massive Creation"

    old_origin = fields.Many2one('mrp.planning.version', 'Current Planning Version', required=True)
    new_origin = fields.Many2one('mrp.planning.version', 'New Planning Version', required=True, domain=[('state', '=', 'open')])
    qty_factor = fields.Float('Quantity Factor', required=True, default=1.0)
    old_product_id = fields.Many2one('product.product', "Old Product", required=True)
    new_product_id = fields.Many2one('product.product', "New Product", required=True)
    old_warehouse_id = fields.Many2one('stock.warehouse', "Old Warehouse", required=True)
    new_warehouse_id = fields.Many2one('stock.warehouse', "New Warehouse", required=True)
    company_id = fields.Many2one('res.company', related='new_warehouse_id.company_id')
    new_user_id = fields.Many2one('res.users', 'New Planning Responsible', required=True, default=lambda self: self.env.user, check_company=True)
    pir_item_ids = fields.Many2many('mrp.independent.requirements', string='Planned Independent Requirements')
    pir_count = fields.Integer('Selected PIRs #', compute='do_count_pir_items', store=True)


    def do_massive_create(self):
        self.ensure_one()
        if self.pir_count == 0:
            raise UserError(_('No Item has been selected'))
        for item in self.pir_item_ids:
            for record in item:
                id_created= self.env['mrp.independent.requirements'].create({
                    'origin': self.new_origin.id,
                    'product_id': self.new_product_id.id,
                    'product_qty': record.product_qty * self.qty_factor,
                    'date_requested': record.date_requested,
                    'uom_id': self.new_product_id.uom_id.id,
                    'warehouse_id' : self.new_warehouse_id.id,
                    'user_id' : self.new_user_id.id,
                })
        return True

    @api.depends('pir_item_ids')
    def do_count_pir_items(self):
        self.pir_count = len(self.pir_item_ids)
        return True

    def _reopen_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new'}

    def do_populate_pir_item(self):
        self.ensure_one()
        selected_pir_items = self.env['mrp.independent.requirements'].search([('origin', '=', self.old_origin.id), ('warehouse_id', '=', self.old_warehouse_id.id), ('product_id', '=', self.old_product_id.id), ('state', '!=', 'cancel')])
        self.pir_item_ids = selected_pir_items
        return self._reopen_form()

