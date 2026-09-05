# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _, SUPERUSER_ID


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'
    _description = 'Work Order'

    def _ctx_production_id(self):
        ctx = self.env.context
        return ctx.get("default_production_id") or (
            ctx.get("active_id") if ctx.get("active_model") == "mrp.production" else False
        )

    @api.onchange("workcenter_id", "operation_id")
    def _onchange_set_production_id_from_ctx(self):
        # This makes it appear in the inline row as soon as user edits something
        pid = self._ctx_production_id()
        for rec in self:
            if not rec.production_id and pid:
                rec.production_id = pid

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        pid = self._ctx_production_id()
        if "production_id" in fields_list and not res.get("production_id") and pid:
            res["production_id"] = pid
        return res

    @api.model_create_multi
    def create(self, vals_list):
        pid = self._ctx_production_id()
        if pid:
            for vals in vals_list:
                if not vals.get("production_id"):
                    vals["production_id"] = pid
        production_ids = {vals.get("production_id") for vals in vals_list if vals.get("production_id")}
        production_map = {
            production.id: production.product_id.name
            for production in self.env["mrp.production"].browse(list(production_ids))
        }
        for vals in vals_list:
            production_id = vals.get("production_id")
            if production_id and not vals.get("x_mo_product_name"):
                vals["x_mo_product_name"] = production_map.get(production_id)
        return super().create(vals_list)


    schedule_sequence = fields.Integer(string='Schedule Seq')
    x_mo_product = fields.Many2one('product.product',related='production_id.product_id')
    x_mo_product_name = fields.Char(string='Part')
    x_wo_delivery_date = fields.Datetime(string='Exp Delivery')
    x_confirmed_date = fields.Date(string='Confirmed Date',related='production_id.x_mrp_confirmed_date')

    def set_scheduled_date(self):
        view_id = self.env.ref('mrp_wo_enhancement.mrp_wo_scheduling_wizard_view_form').id
        return {
            'name': "MRP WO Scheduling",
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mrp.wo.scheduling.wizard',
            'target': 'new',
            'views': [(view_id, 'form')],
            'context': {
                'mrp_workorder_ids': self.ids,
            }
        }

    def action_open_update_frame_wizard(self):
        return {
            'name': _('Update Frame No'),
            'type': 'ir.actions.act_window',
            'res_model': 'update.frame.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': self.ids,
            },
        }

    def create_material_request(self):
        already_exists = []
        newly_created = []

        for rec in self:
            # Check if MR already exists for this MO
            existing = self.env['project.mrequest'].search([
                ('production_id', '=', rec.production_id.id)
            ], limit=1)

            if existing:
                already_exists.append(rec.name or rec.id)
                continue  # Skip this WO

            request_id = self.env['project.mrequest'].create({
                'production_id': rec.production_id.id,
                'workcenter_id': rec.workcenter_id.id
            })
            material_request_line = []
            for move_raw_rec in rec.production_id.move_raw_ids:
                material_request_line.append((0, 0, {
                    'product': move_raw_rec.product_id.id if move_raw_rec.product_id else False,
                    'quantity': move_raw_rec.product_uom_qty,
                    'done_quantity': move_raw_rec.quantity_done,
                    'unit': move_raw_rec.product_uom.id,
                }))
            request_id.mrequest_lines = material_request_line
            request_id.request()

            component_pickings = rec.production_id.picking_ids.filtered(
                lambda p: p.state != 'cancel' and any(
                    m.product_id in rec.production_id.move_raw_ids.mapped('product_id')
                    for m in p.move_lines
                )
            )
            component_pickings.write({'mrequest_id': request_id.id})
            newly_created.append(rec.name or rec.id)

        # Handle notifications
        if already_exists and not newly_created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Warning',
                    'message': 'Material Request already exists for selected Work Order(s).',
                    'sticky': False,
                    'type': 'warning',
                }
            }

        if already_exists and newly_created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Partial Success',
                    'message': f'Material Requests created for some Work Orders. Already existed for others.',
                    'sticky': False,
                    'type': 'info',
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                }
            }

        # All newly created
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Material Requests created successfully.',
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    # def create_material_request(self):
    #     for rec in self:
    #         request_id = self.env['project.mrequest'].create({
    #             'production_id': rec.production_id.id,
    #             'workcenter_id': rec.workcenter_id.id
    #         })
    #         material_request_line = []
    #         for move_raw_rec in rec.production_id.move_raw_ids:
    #             material_request_line.append((0, 0, {
    #                 'product': move_raw_rec.product_id and move_raw_rec.product_id.id or False,
    #                 'quantity': move_raw_rec.product_uom_qty,
    #                 'done_quantity': move_raw_rec.quantity_done
    #             }))
    #         request_id.mrequest_lines = material_request_line
    #         request_id.request()
    #         component_pickings = rec.production_id.picking_ids.filtered(
    #             lambda p: p.state != 'cancel' and any(
    #                 m.product_id in rec.production_id.move_raw_ids.mapped('product_id')
    #                 for m in p.move_lines
    #             )
    #         )

    #         # Assign material request ID to those pickings
    #         component_pickings.write({'mrequest_id': request_id.id})

    #     return {
    #     'type': 'ir.actions.client',
    #     'tag': 'display_notification',
    #     'params': {
    #         'title': 'Success',
    #         'message': 'Material Request created successfully.',
    #         'sticky': False,
    #         'type': 'success',
    #         'next': {
    #             'type': 'ir.actions.client',
    #             'tag': 'reload',
    #                 }
    #             }
    #         }
