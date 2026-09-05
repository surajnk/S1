from odoo import api, fields, models
from odoo.exceptions import UserError



class BillOfLeadingWiz(models.Model):
    _name = 'bill.of.leading.wiz'
    _rec_name = 'bill_auto_no'
    _description = 'Bill Of Lading'

    def get_default_bill_no(self):
        """"""
        seq = self.env['ir.sequence'].next_by_code('bill.of.leading')
        return seq

    ship_date = fields.Date('Ship Date')
    bill_auto_no = fields.Char('Bill Number', default=get_default_bill_no)
    is_manual_bill_no = fields.Boolean('Add Manually Bill Number')
    bill_manual_no = fields.Char('Bill No')
    kind_of_package = fields.Char('Kind Of Package', default='Kraft Wrapping Paper')
    class_or_rate = fields.Char('Class & Rate', default='151320 / Class 55')
    for_payment_send_bill_to_id = fields.Many2one('account.incoterms', 'For Payment, Send Bill To')
    ship_via_id = fields.Many2one('ship.via', string='Ship Via')
    partner_id = fields.Many2one('res.partner', 'Customer')
    address_partner_id = fields.Many2one('res.partner', 'Bill To Address')
    delivery_order_ids = fields.Many2many('stock.picking', 'rel_tbl_bol_del', 'bill_id', 'del_id', 'Delivery Orders')
    total_weight_density = fields.Float(
        'Total Weight (lbs)', compute='_compute_density', store=True, digits=(12, 2))
    total_cubic_feet = fields.Float(
        'Total Cubic Feet', compute='_compute_density', store=True, digits=(12, 2))
    density = fields.Float(
        'Density (lbs/f3)', compute='_compute_density', store=True, digits=(12, 2))
    computed_class = fields.Char(
        'Computed Class', compute='_compute_density', store=True)

    @api.depends('delivery_order_ids', 'delivery_order_ids.move_line_ids.result_package_id')
    def _compute_density(self):
        for rec in self:
            packages = rec.delivery_order_ids.mapped('move_line_ids.result_package_id').filtered(lambda p: p)
            packages = packages.browse(set(packages.ids))

            total_weight = sum(packages.mapped('shipping_weight'))
            total_cubic_feet = 0.0
            for pak in packages:
                if pak.x_length and pak.x_width and pak.x_height:
                    total_cubic_feet += (pak.x_length * pak.x_width * pak.x_height) / 1728.0

            rec.total_weight_density = total_weight
            rec.total_cubic_feet = total_cubic_feet
            rec.density = (total_weight / total_cubic_feet) if total_cubic_feet else 0.0
            rec.computed_class = self.env['nmfc.density.class'].get_class_from_density(rec.density)

    def action_apply_computed_class(self):
        self.ensure_one()
        if not self.computed_class:
            raise UserError(_(
                "No package dimensions found on the selected delivery orders' "
                "packages — set Height/Width/Length on the package(s) first."))
        code = ''
        if self.class_or_rate and ' / ' in self.class_or_rate:
            code = self.class_or_rate.split(' / ')[0].strip()
        new_value = ('%s / Class %s' % (code, self.computed_class)) if code \
            else ('Class %s' % self.computed_class)
        self.write({'class_or_rate': new_value})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'bill.of.leading.wiz',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('ef_stock.bill_of_leading_wiz_form_view').id,
            'target': 'new',
        }
    # def action_apply_computed_class(self):
    #     """Push the computed NMFC class into the Class & Rate field, preserving
    #     any NMFC code the user already entered before ' / '."""
    #     for rec in self:
    #         if not rec.computed_class:
    #             raise UserError(_(
    #                 "No package dimensions found on the selected delivery orders' "
    #                 "packages — set Height/Width/Length on the package(s) first."))
    #         code = ''
    #         if rec.class_or_rate and ' / ' in rec.class_or_rate:
    #             code = rec.class_or_rate.split(' / ')[0].strip()
    #         rec.class_or_rate = ('%s / Class %s' % (code, rec.computed_class)) if code \
    #             else ('Class %s' % rec.computed_class)

    # @api.onchange('partner_id')
    # def _onchange_partner_id(self):
    #     """Update payment bill-to based on the selected partner."""
    #     if self.partner_id:
    #         self.for_payment_send_bill_to_id = self.partner_id.x_freight_terms

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for rec in self:
            freight = False
            if rec.partner_id:
                if rec.partner_id.x_freight_terms:
                    freight = rec.partner_id.x_freight_terms
                elif rec.partner_id.parent_id and rec.partner_id.parent_id.x_freight_terms:
                    freight = rec.partner_id.parent_id.x_freight_terms

                if rec.partner_id.x_ship_via:
                    ship_via = rec.partner_id.x_ship_via
                elif rec.partner_id.parent_id and rec.partner_id.parent_id.x_ship_via:
                    ship_via = rec.partner_id.parent_id.x_ship_via

            rec.for_payment_send_bill_to_id = freight
            rec.ship_via_id = ship_via


    def print_bill_of_leading(self):
        """
        print bill of leading
        """
        bill_no = self.bill_manual_no if self.is_manual_bill_no else self.bill_auto_no
        bol_at = ''
        bol_from = 'Ecological Fibers'
        no_package = {}
        pack_weight = 0
        purchase_rec = ''
        for do_line in self.delivery_order_ids:
            if do_line.branch_id:
                bol_at = do_line.branch_id.address
                bol_from = do_line.branch_id.address_to
            packages = do_line.move_line_ids.mapped('result_package_id').filtered(lambda p: p)
            packages = packages.browse(set(packages.ids))
            for pak in packages:
                pak_type = pak.packaging_id and pak.packaging_id.name or 'Undefined'
                pack_weight += pak.shipping_weight
                if pak_type in no_package:
                    no_package[pak_type] = no_package[pak_type] + 1
                else:
                    no_package.update({pak_type: 1})
            if do_line.origin:
                so_rec = self.env['sale.order'].search([('name', '=', do_line.origin)])
                if so_rec and so_rec.client_order_ref:
                    purchase_rec = purchase_rec + '                    ' + so_rec.client_order_ref

        partner_name = self.partner_id.name
        address_partner_rec = self.address_partner_id and self.address_partner_id or self.partner_id
        datas = {
            'ids': self.ids,
            'model': 'bill.of.leading.wiz',
            'data': {
                'ship_date': self.ship_date,
                'bill_no': bill_no,
                'delivery_order_ids': self.delivery_order_ids,
                'for_payment_send_bill_to': self.for_payment_send_bill_to_id and self.for_payment_send_bill_to_id.name,
                'bol_at': bol_at,
                'bol_from': bol_from,
                'partner_name': partner_name,
                'address_partner_name': address_partner_rec.name,
                'address_partner_street': address_partner_rec.street,
                'address_partner_street2': address_partner_rec.street2,
                'address_partner_mobile': address_partner_rec.mobile or address_partner_rec.phone,
                'address_partner_email': address_partner_rec.email,
                'no_package': no_package,
                'kind_of_package': self.kind_of_package,
                'class_or_rate': self.class_or_rate,
                'ship_via_name': self.ship_via_id.x_name or '',
                'pack_weight': pack_weight,
                'purchase_rec': purchase_rec,
            }
        }

        # docids = self.env['sale.order'].search([]).ids
        return self.env.ref('ef_stock.action_report_bill_of_leading').report_action(None, data=datas)

    def create_bill_of_leading(self):
        print('created')
