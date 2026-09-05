# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MergeMrpWizardLine(models.TransientModel):
    _name = 'sh.merge.mrp.wizard.line'
    _description = 'Merge Mrp Wizard Line'

    merge_line_id = fields.Many2one(
        'sh.merge.mrp.order.wizard', string='Merge Mrp Wizard Line')
    qty = fields.Float(string='Quantity')
    product_id = fields.Many2one(
        'product.product', string='Product')
    mrp_order_line_id = fields.Many2one(
        "stock.move", string="Mrp Order Line")
    mrp_order_id = fields.Many2one("mrp.production", string="Mrp Order")
    qty_available = fields.Float('Quantity On Hand', related="product_id.qty_available", store=True)

class ShMergeMrpOrderWizard(models.TransientModel):
    _name = "sh.merge.mrp.order.wizard"
    _description = "Merge MRP Order Wizard"

    product_id = fields.Many2one('product.product', 'Product')
    mrp_order_id = fields.Many2one("mrp.production", string="Mrp Order")
    mrp_order_ids = fields.Many2many(
        "mrp.production", string="Mrp Orders")
    location_src_id = fields.Many2one('stock.location', 'Components Location')
    location_dest_id = fields.Many2one(
        'stock.location', 'Finished Products Location')
    merge_type = fields.Selection([
        ("nothing_new", "New Order and Do Nothing with selected mrp orders"),
        ("cancel_new", "New Order and Cancel selected mrp orders"),
        ("remove_new", "New Order and Remove selected mrp orders"),
        ("nothing_existing", "Existing Order and Do Nothing with selected mrp orders"),
        ("cancel_existing", "Existing Order and Cancel selected mrp orders"),
        ("remove_existing", "Existing Order and Remove selected mrp orders"),
    ], string="Merge Type")

    merge_line_ids = fields.One2many(
        'sh.merge.mrp.wizard.line', 'merge_line_id', string='Merge Mrp Wizard')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 default=lambda self: self.env.company)

    def action_merge_mrp_order(self):
        order_list = []
        mrp_orders = []
        if self and self.mrp_order_ids:
            if self.mrp_order_id:
                for mrp in self.env['mrp.production'].sudo().browse(self.env.context.get('active_ids')):
                    if mrp.name not in mrp_orders:
                        mrp_orders.append(mrp.name)
                source = ','.join(mrp_orders)
                order_list.append(self.mrp_order_id.id)
                sequence = 10
                orders = self.env['mrp.production'].sudo().search(
                    [('id', '!=', self.mrp_order_id.id), ('id', 'in', self.mrp_order_ids.ids)], order='id asc')
                product_qty = self.mrp_order_id.product_qty
                x_order_master_yards = self.mrp_order_id.x_order_master_yards
                for order in orders:
                    for merge in self.merge_line_ids:
                        if merge.mrp_order_id.id == order.id:
                            if self.company_id.sh_mrp_sub_merge_qty:
                                if merge.qty <= order.product_qty:
                                    SO = order.product_qty - merge.qty
                                    if SO > 0:
                                        order.product_qty = SO
                                        product_qty += merge.qty
                                        x_order_master_yards += merge.mrp_order_id.x_order_master_yards
                                    else:
                                        self.mrp_order_id._onchange_product_qty()
                                        self.mrp_order_id._onchange_move_raw()
                                        self.mrp_order_id._onchange_move_finished()
                                        sequence += 1

                                        product_qty += merge.qty
                                        x_order_master_yards += merge.mrp_order_id.x_order_master_yards

                                        order.unlink()
                                else:
                                    raise UserError(
                                        _("%s Quantity is can't be more than %s Manufacturing Order's Quantity (%s)") % (merge.product_id.name, order.name, order.product_uom_qty))
                            else:
                                if merge.qty > order.product_qty:
                                    raise UserError(
                                        _("%s Quantity is can't be more than %s Manufacturing Order's Quantity (%s)") % (merge.product_id.name, order.name, order.product_uom_qty))
                                else:
                                    product_qty += merge.qty
                                    x_order_master_yards += merge.mrp_order_id.x_order_master_yards
                            self.mrp_order_id.product_qty = product_qty
                            self.mrp_order_id.x_order_master_yards = x_order_master_yards
                            self.mrp_order_id._onchange_product_qty()
                            self.mrp_order_id._onchange_move_raw()
                            self.mrp_order_id._onchange_move_finished()
                            if order.exists():

                                sequence += 1
                                if self.merge_type == "cancel_existing":
                                    order.sudo().action_cancel()
                                    order_list.append(order.id)
                                elif self.merge_type == "remove_existing":
                                    order.sudo().action_cancel()
                                    order.sudo().unlink()

                self.mrp_order_id.origin = source
                if self.env.company.notify_in_chatter:
                    message = '<p>This Existing mrp order has been updated from '
                    message += ','.join(mrp_orders) + str('</p>')
                    self.env['mail.message'].sudo().create({
                        'subtype_id': self.env.ref('mail.mt_comment').id,
                        'date': fields.Datetime.now(),
                        'email_from': self.env.user.partner_id.email_formatted,
                        'message_type': 'comment',
                        'model': 'mrp.production',
                        'res_id': self.mrp_order_id.id,
                        'record_name': self.mrp_order_id.name,
                        'body': message
                    })

            else:
                order_line_vals = {}
                created_mo = self.mrp_order_ids[0].copy(
                    default=order_line_vals)
                for mrp in self.env['mrp.production'].sudo().browse(self.env.context.get('active_ids')):
                    if mrp.name not in mrp_orders:
                        mrp_orders.append(mrp.name)
                source = ','.join(mrp_orders)
                if created_mo:
                    order_list.append(created_mo.id)
                    order_line_vals = {}
                    sequence = 10
                    orders = self.env['mrp.production'].sudo().search(
                        [('id', 'in', self.mrp_order_ids.ids)], order='id asc')
                    product_qty = 0
                    x_order_master_yards = 0
                    for order in orders:
                        for merge in self.merge_line_ids:
                            if merge.mrp_order_id.id == order.id:
                                if self.company_id.sh_mrp_sub_merge_qty:
                                    if merge.qty <= order.product_qty:
                                        SO = order.product_qty - merge.qty
                                        if SO > 0:
                                            order.product_qty = SO
                                            product_qty += merge.qty
                                        else:
                                            created_mo._onchange_product_qty()
                                            created_mo._onchange_move_raw()
                                            created_mo._onchange_move_finished()
                                            sequence += 1

                                            product_qty += merge.qty
                                            x_order_master_yards += merge.mrp_order_id.x_order_master_yards
                                            order.unlink()
                                    else:
                                        raise UserError(
                                            _("%s Quantity is can't be more than %s Manufacturing Order's Quantity (%s)") % (merge.product_id.name, order.name, order.product_uom_qty))
                                else:
                                    if merge.qty > order.product_qty:
                                        raise UserError(
                                            _("%s Quantity is can't be more than %s Manufacturing Order's Quantity (%s)") % (merge.product_id.name, order.name, order.product_uom_qty))
                                    else:
                                        product_qty += merge.qty
                                        x_order_master_yards += merge.mrp_order_id.x_order_master_yards

                                created_mo.write({
                                    'product_qty': product_qty,
                                    'x_order_master_yards': x_order_master_yards
                                })
                                created_mo._onchange_product_qty()
                                created_mo._onchange_move_raw()
                                created_mo._onchange_move_finished()
                                if order.exists():
                                    sequence += 1
                                    if self.merge_type == "cancel_new":
                                        order.sudo().action_cancel()
                                        order_list.append(order.id)
                                    elif self.merge_type == "remove_new":
                                        order.sudo().action_cancel()
                                        order.sudo().unlink()
                    created_mo.origin = source
                    if self.env.company.notify_in_chatter:
                        message = '<p>This Existing mrp order has been updated from '
                        message += ','.join(mrp_orders) + str('</p>')
                        self.env['mail.message'].sudo().create({
                            'subtype_id': self.env.ref('mail.mt_comment').id,
                            'date': fields.Datetime.now(),
                            'email_from': self.env.user.partner_id.email_formatted,
                            'message_type': 'comment',
                            'model': 'mrp.production',
                            'res_id': created_mo.id,
                            'record_name': created_mo.name,
                            'body': message
                        })

            if order_list:
                return {
                    "name": _("Manufacturing Orders"),
                    "domain": [("id", "in", order_list)],
                    "view_type": "form",
                    "view_mode": "tree,form",
                    "res_model": "mrp.production",
                    "view_id": False,
                    "type": "ir.actions.act_window",
                }

    @api.model
    def default_get(self, fields):
        rec = super(ShMergeMrpOrderWizard, self).default_get(fields)
        active_ids = self._context.get("active_ids")
        line_list = []

        if not active_ids:
            raise UserError(
                _("Programming error: wizard action executed without active_ids in context."))

        if len(self._context.get("active_ids", [])) < 2:
            raise UserError(
                _("Please Select atleast two mrp orders to perform merge operation."))

        mrp_orders = self.env["mrp.production"].browse(active_ids)

        if any(order.state not in ["draft", "confirmed", "progress"] for order in mrp_orders):
            raise UserError(
                _("You can only merge mrp orders which are in Draft/Confirmed/In Progress state"))

        for res in mrp_orders:
            if res.move_raw_ids:
                line_vals = {
                    'product_id': res.product_id.id,
                    'qty': res.product_qty,
                    'mrp_order_id': res.id,
                }
                line_list.append((0, 0, line_vals))

        if len(mrp_orders.ids) > 0:
            first_product = mrp_orders[0].product_id
            rec.update({
                'product_id': first_product.id
            })
            for order in mrp_orders:
                if order.product_id.id != first_product.id:
                    raise UserError(
                        _("You can only merge mrp orders which are in same product/bill of material. "))
        if self.env.company.merge_type:
            rec.update({
                'merge_type': self.env.company.merge_type
            })
        rec.update({
            "mrp_order_ids": [(6, 0, mrp_orders.ids)],
            "merge_line_ids": line_list,
        })
        return rec
