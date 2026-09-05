from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_product_type = fields.Selection([
        ('rawmaterial', 'Raw Material'),
        ('manufacturedproduct', 'Manufactured Product'),
        ('purchasedproduct', 'Purchased Product')], 'Product Type(EF)')
    x_FSC = fields.Selection([
        ('notfsc', 'NOT FSC'),
        ('fscmixcredit', 'FSC MIX CREDIT : PBN-COC-003258'),
        ('fscrecycled', 'FSC RECYCLED 100 PERCENT : PBN-COC-003258'),
        ('fscrecycledcredit', 'FSC RECYCLED CREDIT : PBN-COC-003258')], 'FSC')
    x_product_item = fields.Many2one('product.item.group','Item Group')
    x_stocked = fields.Boolean('Stocked?')
    x_embossing_allowed = fields.Boolean('Embossing Allowed?')
    x_retail_sale_item = fields.Boolean('Retail Sale Item')
    x_consignment_item = fields.Boolean('Consignment Item')
    x_ExtReference = fields.Char(string='External Reference')
    x_item_width = fields.Float('Item Width',digits='EF Product')
    x_item_length = fields.Float('Item Length',digits='EF Product')
    x_product_price_group = fields.Many2one('price.group','Price Group')
    x_class_code_group = fields.Many2one('class.code','Class Code')
    x_class_commodity_group = fields.Many2one('product.commodity.code','Commodity Code')
    x_retail_barcode = fields.Char('Retail Barcode')
    x_retail_description = fields.Char('Retail Description')
    x_retail_short_description = fields.Char('Retail Short Description')
    x_retail_pack_size = fields.Integer('Retail Pack Size')
    x_retail_packbox = fields.Char('Retail Pack/Box')
    x_retail_part = fields.Char('Retail Part Number')
    x_retail_size_desc = fields.Char('Retail Size Description')
    x_retail_pack_label = fields.Char('Retail Pack Label')
    x_retail_box_label = fields.Char('Retail Box Label')
    x_break_qty_price = fields.One2many('product.quantity','product_tmplt_id','Quantity Breaks',copy=True)
    x_minimum_qty = fields.Integer('Minimum Quantity')
    x_maximum_qty = fields.Integer('Maximum Quantity')
    x_reorder_qty = fields.Integer('Re-Order Quantity')
    x_tolerances = fields.Char('Tolerances')
    x_tolerances_m2 = fields.Many2one('product.tolerance','Tolerance(Lvl)')
    x_qty_grid_break_code = fields.Many2one('product.break.codes','Price Group Quantity Break Code')
    x_qty_grid_break_code_chg = fields.Many2one('product.break.codes','Quantity Break Code')
    x_product_wc = fields.Many2many('mrp.workcenter',string='Machines')
    x_product_workcenter =  fields.Many2many('mrp.workcenter','product_workcenter_rel','prod_id','workcent_id',string="WorkCenters")
    x_product_emboss = fields.One2many('product.embosser','x_product_embosser','Embossers')
    x_product_conversion = fields.Many2one('product.product','Convert To')
    x_product_bc_visibility = fields.Boolean('Break',default=False)
    x_product_embossing = fields.Many2one('product.embossing','Embossing')
    on_wo_quantity = fields.Float(string="W/O Quantity", compute="compute_on_wo_quantity")
    on_po_quantity = fields.Float(string="PO Quantity", compute="compute_on_po_quantity")
    on_so_quantity = fields.Float(string="Stock Order Quantity", compute="compute_on_so_quantity")
    x_product_novaflow = fields.Many2one('product.novaflow','Novaflow')
    free_qty = fields.Float(
        'Free To Use Quantity',
        compute='_compute_free_qty',
        digits='Product Unit of Measure',
    )

    allocated_qty = fields.Float(
        'Allocated Quantity',
        compute='_compute_allocated_qty',
        digits='Product Unit of Measure',
    )

    on_order_quantity = fields.Float(
        string="On Order",
        compute="_compute_on_order_quantity",
        digits='Product Unit of Measure',
    )

    nrc_quantity = fields.Float(
        string="NCR Quantity",
        compute='_compute_nrc_quantity',
        digits='Product Unit of Measure',
    )

    pending_receive_qty = fields.Float(
        string="Pending to Receive",
        compute="_compute_on_order_quantity",
        digits='Product Unit of Measure',
    )

    def _compute_nrc_quantity(self):
        for tmpl in self:
            tmpl.nrc_quantity = sum(tmpl.product_variant_ids.mapped('nrc_quantity'))

    def _get_open_mos_and_so_names(self):
        """Open MOs for these templates + set of origins that are Sale Orders."""
        mos = self.env['mrp.production'].search([
            ('state', 'in', ('confirmed', 'progress')),
            ('product_id.product_tmpl_id', 'in', self.ids),
        ])
        origins = list(set(mos.filtered(lambda m: m.origin).mapped('origin')))
        so_names = set(self.env['sale.order'].search(
            [('name', 'in', origins)]).mapped('name'))
        return mos, so_names

    def _compute_free_qty(self):
        quants = self.env['stock.quant'].search([
            ('product_id.product_tmpl_id', 'in', self.ids),
            ('location_id.usage', '=', 'internal'),
            ('location_id.x_exclude_from_available', '=', True),
        ])
        excluded = {}
        for q in quants:
            tmpl_id = q.product_id.product_tmpl_id.id
            excluded[tmpl_id] = excluded.get(tmpl_id, 0.0) + q.quantity

        for tmpl in self:
            nrc = sum(tmpl.product_variant_ids.mapped('nrc_quantity'))
            tmpl.free_qty = tmpl.qty_available - (tmpl.allocated_qty + nrc + excluded.get(tmpl.id, 0.0))

    def _compute_allocated_qty(self):
        # Part A: this product used as a COMPONENT in open MOs (demand)
        comp_data = {}
        raw_moves = self.env['stock.move'].search([
            ('raw_material_production_id', '!=', False),
            ('raw_material_production_id.state', 'in', ('confirmed', 'progress')),
            ('product_id.product_tmpl_id', 'in', self.ids),
            ('state', 'not in', ('done', 'cancel')),
        ])
        for mv in raw_moves:
            tmpl_id = mv.product_id.product_tmpl_id.id
            comp_data[tmpl_id] = comp_data.get(tmpl_id, 0.0) + mv.product_uom_qty

        # Part B: this product MANUFACTURED via SO-originated MOs
        mos, so_names = self._get_open_mos_and_so_names()
        prod_data = {}
        for m in mos:
            if m.origin and m.origin in so_names:
                tmpl_id = m.product_id.product_tmpl_id.id
                prod_data[tmpl_id] = prod_data.get(tmpl_id, 0.0) + max(m.product_qty - m.qty_produced, 0.0)

        for tmpl in self:
            tmpl.allocated_qty = comp_data.get(tmpl.id, 0.0) + prod_data.get(tmpl.id, 0.0)

    def _compute_on_order_quantity(self):
        # ---- MO side: non-SO open MOs ----
        mos, so_names = self._get_open_mos_and_so_names()
        mo_data = {}
        for m in mos:
            if m.origin and m.origin in so_names:
                continue
            tmpl_id = m.product_id.product_tmpl_id.id
            mo_data[tmpl_id] = mo_data.get(tmpl_id, 0.0) + max(m.product_qty - m.qty_produced, 0.0)

        # ---- PO side: full converted (on order) + pending converted ----
        po_ordered = {}
        po_pending = {}
        po_lines = self.env['purchase.order.line'].search([
            ('order_id.state', 'in', ('purchase', 'done')),
            ('product_id.product_tmpl_id', 'in', self.ids),
        ])
        for l in po_lines:
            if l.product_qty <= 0:
                continue
            tmpl_id = l.product_id.product_tmpl_id.id

            if l.converted_product_qty > 0:
                ordered_conv = l.converted_product_qty
            else:
                ordered_conv = l.product_uom._compute_quantity(
                    l.product_qty, l.product_id.uom_id)
            po_ordered[tmpl_id] = po_ordered.get(tmpl_id, 0.0) + ordered_conv

            pending = max(l.product_qty - l.qty_received, 0.0)
            if pending > 0:
                ratio = pending / l.product_qty
                po_pending[tmpl_id] = po_pending.get(tmpl_id, 0.0) + ordered_conv * ratio

        for rec in self:
            rec.on_order_quantity = mo_data.get(rec.id, 0.0) + po_ordered.get(rec.id, 0.0)
            rec.pending_receive_qty = po_pending.get(rec.id, 0.0)

    ###BEFORE CONVERTED QUANTITY#######
    # def _compute_on_order_quantity(self):
    #     # pending qty on NON-SO open MOs + pending confirmed PO qty
    #     mos, so_names = self._get_open_mos_and_so_names()
    #     mo_data = {}
    #     for m in mos:
    #         if m.origin and m.origin in so_names:
    #             continue  # SO-originated -> belongs to Allocated, not On Order
    #         tmpl_id = m.product_id.product_tmpl_id.id
    #         mo_data[tmpl_id] = mo_data.get(tmpl_id, 0.0) + max(m.product_qty - m.qty_produced, 0.0)

    #     po_data = {}
    #     po_lines = self.env['purchase.order.line'].search([
    #         ('order_id.state', 'in', ('purchase', 'done')),
    #         ('product_id.product_tmpl_id', 'in', self.ids),
    #     ])
    #     for l in po_lines:
    #         tmpl_id = l.product_id.product_tmpl_id.id
    #         po_data[tmpl_id] = po_data.get(tmpl_id, 0.0) + max(l.product_qty - l.qty_received, 0.0)

    #     for rec in self:
    #         rec.on_order_quantity = mo_data.get(rec.id, 0.0) + po_data.get(rec.id, 0.0)

    def action_view_on_order_details(self):
        self.ensure_one()
        wizard = self.env['on.order.detail.wizard'].create({'product_tmpl_id': self.id})
        wizard._populate_lines()
        return {
            'name': 'On Order - %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'on.order.detail.line',
            'view_mode': 'tree',
            'domain': [('wizard_id', '=', wizard.id)],
            'context': {'group_by': 'order_type'},
            'target': 'new',
        }

    def action_view_allocated_details(self):
        self.ensure_one()
        wizard = self.env['on.order.detail.wizard'].create({'product_tmpl_id': self.id})
        wizard._populate_allocated_lines()
        return {
            'name': 'Allocated MOs - %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'on.order.detail.line',
            'view_mode': 'tree',
            'domain': [('wizard_id', '=', wizard.id)],
            'context': {'group_by': 'order_type'},
            'target': 'new',
        }

    def action_view_ncr_details(self):
        self.ensure_one()
        wizard = self.env['on.order.detail.wizard'].create({'product_tmpl_id': self.id})
        wizard._populate_ncr_lines()
        return {
            'name': 'NCR - %s' % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'on.order.detail.line',
            'view_mode': 'tree',
            'domain': [('wizard_id', '=', wizard.id)],
            'context': {'group_by': 'order_type'},
            'target': 'new',
        }

    # def _compute_nrc_quantity(self):
    #     for tmpl in self:
    #         tmpl.nrc_quantity = sum(tmpl.product_variant_ids.mapped('nrc_quantity'))

    # def _compute_on_order_quantity(self):
    #     # ---- MO side: open MOs NOT originated from Sale Orders ----
    #     mo_data = {}
    #     mos = self.env['mrp.production'].search([
    #         ('state', 'in', ('confirmed', 'progress', 'to_close')),
    #         ('product_id.product_tmpl_id', 'in', self.ids),
    #         ('source','!=',False)
    #     ])
    #     for m in mos:
    #         tmpl_id = m.product_id.product_tmpl_id.id
    #         mo_data[tmpl_id] = mo_data.get(tmpl_id, 0.0) + max(m.product_qty - m.qty_produced, 0.0)


    #     po_data = {}
    #     po_lines = self.env['purchase.order.line'].search([
    #         ('order_id.state', 'in', ('purchase', 'done')),
    #         ('product_id.product_tmpl_id', 'in', self.ids),
    #     ])
    #     for l in po_lines:
    #         tmpl_id = l.product_id.product_tmpl_id.id
    #         po_data[tmpl_id] = po_data.get(tmpl_id, 0.0) + max(l.product_qty - l.qty_received, 0.0)

    #     for rec in self:
    #         rec.on_order_quantity = mo_data.get(rec.id, 0.0) + po_data.get(rec.id, 0.0)

    # def action_view_on_order_details(self):
    #     self.ensure_one()
    #     wizard = self.env['on.order.detail.wizard'].create({'product_tmpl_id': self.id})
    #     wizard._populate_lines()
    #     return {
    #         'name': 'On Order - %s' % self.name,
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'on.order.detail.line',
    #         'view_mode': 'tree',
    #         'domain': [('wizard_id', '=', wizard.id)],
    #         'context': {'group_by': 'order_type'},
    #         'target': 'new',
    #     }


    # def _compute_allocated_qty(self):
    #     for tmpl in self:
    #         variant_free = sum(tmpl.product_variant_ids.mapped('free_qty'))
    #         tmpl.allocated_qty = tmpl.qty_available - variant_free

    # def _compute_free_qty(self):
    #     for tmpl in self:
    #         free = sum(tmpl.product_variant_ids.mapped('free_qty'))
    #         nrc = sum(tmpl.product_variant_ids.mapped('nrc_quantity'))
    #         tmpl.free_qty = free - nrc

    # def _compute_allocated_qty(self):
    #     for tmpl in self:
    #         tmpl.allocated_qty = tmpl.qty_available - tmpl.free_qty
            
    # def _compute_free_qty(self):
    #     for tmpl in self:
    #         tmpl.free_qty = sum(tmpl.product_variant_ids.mapped('free_qty'))

    def compute_on_wo_quantity(self):
        for rec in self:
            rec.on_wo_quantity = sum(
                self.env['mrp.production'].search([('state', 'in', ('confirmed', 'progress'))]).move_raw_ids.filtered
                (lambda x: x.product_id.product_tmpl_id.id == rec.id).mapped('quantity_done'))

    def compute_on_po_quantity(self):
        for rec in self:
            rec.on_po_quantity = sum(
                self.env['purchase.order'].search([('state', '=', 'purchase')]).order_line.filtered
                (lambda x: x.product_id.product_tmpl_id.id == rec.id).mapped('qty_received'))

    def compute_on_so_quantity(self):
        for rec in self:
            rec.on_so_quantity = sum(
                self.env['mrp.production'].search(
                    [('state', 'in', ('confirmed', 'progress')), ('origin', '=', False)]).move_raw_ids.filtered
                (lambda x: x.product_id.product_tmpl_id.id == rec.id).mapped('quantity_done'))


    @api.onchange('categ_id')
    def fetch_breakpts(self):
        for rec in self:
            if rec.categ_id:
                self.x_class_commodity_group = rec.categ_id.x_class_commodity_category_group.id
                self.x_class_code_group = rec.categ_id.x_class_code_category_group.id
                self.x_product_item = rec.categ_id.x_product_category_item.id
                self.x_product_price_group = rec.categ_id.x_product_price_category_group.id
                res=[(5,0,0)]
                for qc in rec.categ_id.x_product_price_category_group.x_qty_break_code.x_no_of_break_quantities_grid:
                    val = {
                    'x_product_qty': qc.x_breakqty
                    }
                    res.append((0,0,val))
                rec.x_break_qty_price = res

    @api.onchange('x_product_price_group')
    def fetch_comm_breakpts(self):
        for rec in self:
            val1={}
            rec.write({'x_break_qty_price': [(5, 0, val1)]})
            if rec.x_product_price_group:
                self.x_product_bc_visibility = True
                self.x_qty_grid_break_code = rec.x_product_price_group.x_qty_break_code
                #self.x_qty_grid_break_code_chg = ''
                res=[(5,0,0)]
                for qc in rec.x_product_price_group.x_sale_price:
                    val = {
                    'x_product_qty': qc.x_price_qty,
                    'x_product_price_per_value': qc.x_selling_price
                    }
                    res.append((0,0,val))
                rec.x_break_qty_price = res
                #rec.x_qty_grid_break_code = rec.x_product_price_group.x_qty_break_code
            else:
                self.x_product_bc_visibility = False
                self.x_qty_grid_break_code = 0
                self.x_qty_grid_break_code_chg = 0

    @api.onchange('x_qty_grid_break_code_chg')
    def fetch_cgrid_breakpts(self):
        for rec in self:
            val2={}
            rec.write({'x_break_qty_price': [(5, 0, val2)]})
            if rec.x_qty_grid_break_code_chg:
                self.x_qty_grid_break_code = ''
                res=[(5,0,0)]
                for qc in rec.x_qty_grid_break_code_chg.x_no_of_break_quantities_grid:
                    val = {
                    'x_product_qty': qc.x_breakqty
                    }
                    res.append((0,0,val))
                rec.x_break_qty_price = res

    # @api.onchange('x_qty_grid_break_code_chg')
    # def fetch_cgrid_breakpts(self):
    #     for rec in self:
    #         if rec.x_qty_grid_break_code_chg:
    #             self.x_qty_grid_break_code = rec.x_qty_grid_break_code_chg.id

class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_product_type = fields.Selection([
        ('rawmaterial', 'Raw Material'),
        ('manufacturedproduct', 'Manufactured Product'),
        ('purchasedproduct', 'Purchased Product')], 'Product Type(EF)',related='product_tmpl_id.x_product_type',readonly=False)
    x_FSC = fields.Selection([
        ('notfsc', 'NOT FSC'),
        ('fscmixcredit', 'FSC MIX CREDIT : NC-COC-003258'),
        ('fscrecycled', 'FSC RECYCLED 100% : NC-COC-003258'),
        ('fscrecycledcredit', 'FSC RECYCLED CREDIT : NC-COC-003258')], 'FSC',related='product_tmpl_id.x_FSC',readonly=False)
    x_product_item = fields.Many2one('product.item.group','Item Group',related='product_tmpl_id.x_product_item',readonly=False)
    x_stocked = fields.Boolean('Stocked?',related='product_tmpl_id.x_stocked',readonly=False)
    x_embossing_allowed = fields.Boolean('Embossing Allowed?',related='product_tmpl_id.x_embossing_allowed',readonly=False)
    x_retail_sale_item = fields.Boolean('Retail Sale Item',related='product_tmpl_id.x_retail_sale_item',readonly=False)
    x_item_width = fields.Float('Item Width',digits='EF Product',related='product_tmpl_id.x_item_width',readonly=False)
    x_item_length = fields.Float('Item Length',digits='EF Product',related='product_tmpl_id.x_item_length',readonly=False)
    x_product_price_group = fields.Many2one('price.group','Price Group',related='product_tmpl_id.x_product_price_group',readonly=False)
    x_class_code_group = fields.Many2one('class.code','Class Code',related='product_tmpl_id.x_class_code_group',readonly=False)
    x_class_commodity_group = fields.Many2one('product.commodity.code','Commodity Code',related='product_tmpl_id.x_class_commodity_group',readonly=False)
    x_retail_barcode = fields.Char('Retail Barcode',related='product_tmpl_id.x_retail_barcode',readonly=False)
    x_retail_description = fields.Char('Retail Description',related='product_tmpl_id.x_retail_description',readonly=False)
    x_retail_short_description = fields.Char('Retail Short Description',related='product_tmpl_id.x_retail_short_description',readonly=False)
    x_retail_pack_size = fields.Integer('Retail Pack Size',related='product_tmpl_id.x_retail_pack_size',readonly=False)
    x_retail_packbox = fields.Char('Retail Pack/Box',related='product_tmpl_id.x_retail_packbox',readonly=False)
    x_retail_part = fields.Char('Retail Part Number',related='product_tmpl_id.x_retail_part',readonly=False)
    x_retail_size_desc = fields.Char('Retail Size Description',related='product_tmpl_id.x_retail_size_desc',readonly=False)
    x_retail_pack_label = fields.Char('Retail Pack Label',related='product_tmpl_id.x_retail_pack_label',readonly=False)
    x_retail_box_label = fields.Char('Retail Box Label',related='product_tmpl_id.x_retail_box_label',readonly=False)
    x_break_qty_price = fields.One2many('product.quantity','product_tmplt_id','Quantity Breaks',related='product_tmpl_id.x_break_qty_price',readonly=False,copy=True)
    x_minimum_qty = fields.Integer('Minimum Quantity',related='product_tmpl_id.x_minimum_qty',readonly=False)
    x_maximum_qty = fields.Integer('Maximum Quantity',related='product_tmpl_id.x_maximum_qty',readonly=False)
    x_reorder_qty = fields.Integer('Re-Order Quantity',related='product_tmpl_id.x_reorder_qty',readonly=False)
    x_tolerances = fields.Char('Tolerances',related='product_tmpl_id.x_tolerances',readonly=False)
    x_tolerances_m2 = fields.Many2one('product.tolerance','Tolerance(Lvl)',related='product_tmpl_id.x_tolerances_m2')
    x_qty_grid_break_code = fields.Many2one('product.break.codes','Quantity Break Code',related='product_tmpl_id.x_qty_grid_break_code',readonly=False)
    x_qty_grid_break_code_chg = fields.Many2one('product.break.codes','Quantity Break Code',related='product_tmpl_id.x_qty_grid_break_code_chg',readonly=False)
    x_product_product_emboss = fields.One2many('product.embosser','x_product_product_embosser','Embossers',related='product_tmpl_id.x_product_emboss',readonly=False)
    x_product_conversion = fields.Many2one('product.product','Convert To',related='product_tmpl_id.x_product_conversion',readonly=False)
    x_product_product_embossing = fields.Many2one('product.embossing','Embossing',related='product_tmpl_id.x_product_embossing',readonly=False,store=True)
    x_product_product_novaflow = fields.Many2one('product.novaflow','Novaflow',related='product_tmpl_id.x_product_novaflow',readonly=False,store=True)
    #x_prod_workcenter = fields.One2many('product.workcenter','product_workcenter_id','Work-Centers',related='product_tmpl_id.x_prod_workcenter',readonly=False)

    def get_product_multiline_description_sale(self):
        """Override to set default_code as the name in sales."""
        name = self.default_code if self.default_code else self.display_name
        return name

    def name_get(self):
        # TDE: this could be cleaned a bit I think

        def _name_get(d):
            name = d.get('name', '')
            # code = self._context.get('display_default_code', True) and d.get('default_code', False) or False
            # if code:
            #     name = '[%s] %s' % (code,name)
            return (d['id'], name)

        partner_id = self._context.get('partner_id')
        if partner_id:
            partner_ids = [partner_id, self.env['res.partner'].browse(partner_id).commercial_partner_id.id]
        else:
            partner_ids = []
        company_id = self.env.context.get('company_id')

        # all user don't have access to seller and partner
        # check access and use superuser
        self.check_access_rights("read")
        self.check_access_rule("read")

        result = []

        # Prefetch the fields used by the `name_get`, so `browse` doesn't fetch other fields
        # Use `load=False` to not call `name_get` for the `product_tmpl_id`
        self.sudo().read(['name', 'default_code', 'product_tmpl_id'], load=False)

        product_template_ids = self.sudo().mapped('product_tmpl_id').ids

        if partner_ids:
            supplier_info = self.env['product.supplierinfo'].sudo().search([
                ('product_tmpl_id', 'in', product_template_ids),
                ('name', 'in', partner_ids),
            ])
            # Prefetch the fields used by the `name_get`, so `browse` doesn't fetch other fields
            # Use `load=False` to not call `name_get` for the `product_tmpl_id` and `product_id`
            supplier_info.sudo().read(['product_tmpl_id', 'product_id', 'product_name', 'product_code'], load=False)
            supplier_info_by_template = {}
            for r in supplier_info:
                supplier_info_by_template.setdefault(r.product_tmpl_id, []).append(r)
        for product in self.sudo():
            variant = product.product_template_attribute_value_ids._get_combination_name()

            name = variant and "%s (%s)" % (product.name, variant) or product.name
            sellers = []
            if partner_ids:
                product_supplier_info = supplier_info_by_template.get(product.product_tmpl_id, [])
                sellers = [x for x in product_supplier_info if x.product_id and x.product_id == product]
                if not sellers:
                    sellers = [x for x in product_supplier_info if not x.product_id]
                # Filter out sellers based on the company. This is done afterwards for a better
                # code readability. At this point, only a few sellers should remain, so it should
                # not be a performance issue.
                if company_id:
                    sellers = [x for x in sellers if x.company_id.id in [company_id, False]]
            if sellers:
                for s in sellers:
                    seller_variant = s.product_name and (
                        variant and "%s (%s)" % (s.product_name, variant) or s.product_name
                        ) or False
                    mydict = {
                              'id': product.id,
                              'name': seller_variant or name,
                              'default_code': s.product_code or product.default_code,
                              }
                    temp = _name_get(mydict)
                    if temp not in result:
                        result.append(temp)
            else:
                mydict = {
                          'id': product.id,
                          'name': name,
                          'default_code': product.default_code,
                          }
                result.append(_name_get(mydict))
        return result

class ProductCategory(models.Model):
    _inherit = 'product.category'

    x_branch_code = fields.Char('Branch Code')
    x_product_price_category_group = fields.Many2one('price.group','Price Group')
    x_class_code_category_group = fields.Many2one('class.code','Class Code')
    x_class_commodity_category_group = fields.Many2one('product.commodity.code','Commodity Code')
    x_product_category_item = fields.Many2one('product.item.group','Item Group')
    x_property_account_inventory_categ_id = fields.Many2one('account.account','WIP')

class ProductQuantity(models.Model):
    _name = 'product.quantity'

    x_product_qty = fields.Char('Quantity Breaks')
    x_product_uom = fields.Many2one('uom.uom', 'Unit of Measure',
        related='product_tmplt_id.uom_id')
    x_product_price_per_uom = fields.Float('Price Per UOM',digits='EF Price')
    x_product_price_per_value = fields.Float('Selling Price',digits='EF Price')
    product_tmplt_id = fields.Many2one(
        'product.template', 'Product Template')

class CustQuantityPricelist(models.Model):
    _name = 'cust.quantity.pricelist'

    x_product_cust_qty_pr = fields.Char('Cust Qty Breaks')
    x_product_cust_unit_price = fields.Float('Cust Unit Price',digits='EF Price')
    product_pricelist_cust_item_id = fields.Many2one('product.pricelist.item','Cust Unit Breaks')

class ProductQuantityPricelist(models.Model):
    _name = 'product.quantity.pricelist'

    x_product_qty_pr = fields.Char('Quantity Breaks')
    x_product_lvl_pr = fields.Char('Level')
    x_product_level_price_pr = fields.Float('Level Price',digits='EF Price')
    x_product_uom_pr = fields.Many2one('uom.uom', 'Unit of Measure',)
    x_product_price_per_uom_pr = fields.Float('Price Per UOM',digits='EF Price')
    x_product_price_per_value_pr = fields.Float('Fixed Price',digits='EF Price')
    x_product_discount_on_level_pr = fields.Float('Discount',digits='EF Price')
    product_pricelist_item_id = fields.Many2one('product.pricelist.item','Pricelist Breaks')

class ProductWorkcenter(models.Model):
    _name = 'product.workcenter'

    # x_product_machines = fields.Many2one('mrp.workcenter','Machines')
    # product_workcenter_id = fields.Many2one('product.template', 'Product Workcenter')

class PricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    x_pricelist_pricing_code = fields.Char('Pricing Code')
    x_pricelist_discount_code = fields.Char('Discount Code')
    x_pricelist_implement = fields.Selection([
        ('current', 'CURRENT')], 'Implement Change')
    x_pricelist_break_qty_price = fields.One2many('product.quantity.pricelist','product_pricelist_item_id','Quantity Breaks')
    x_pricelist_break_cust_qty_price = fields.One2many('cust.quantity.pricelist','product_pricelist_cust_item_id','Cust Unit Breaks')
    x_pricelist_break_code = fields.Many2one('product.break.codes','Quantity Break Code')
    x_pricelist_pricegroup_breakcode = fields.Many2one('product.break.codes','Price Group Break Code')
    use_cust_units = fields.Selection(
        [('customer_units', 'Customer Units'), 
         ('master_yards', 'Master Yards')], 
        string="Unit Type", 
        default='customer_units',)


    @api.onchange('x_pricelist_break_code','product_tmpl_id','price_group_id')
    def _onchange_pricelist_break_code(self):
        for rec in self:
            lines = [(5, 0, 0)]  # clear table first

            # precedence: price_group > break_code > product_template
            if rec.price_group_id:
                # FIX #2: write on rec, not self
                rec.x_pricelist_pricegroup_breakcode = rec.price_group_id.x_qty_break_code
                for qc in rec.price_group_id.x_sale_price:
                    lines.append((0, 0, {
                        'x_product_qty_pr': qc.x_price_qty,  # Char; numeric is fine too, Odoo will cast
                        # populate more fields here if your price-group holds them
                        'x_product_price_per_value_pr':qc.x_selling_price,
                    }))

            elif rec.x_pricelist_break_code:
                for qc in rec.x_pricelist_break_code.x_no_of_break_quantities_grid:
                    lines.append((0, 0, {
                        'x_product_qty_pr': qc.x_breakqty,
                    }))

            elif rec.product_tmpl_id:
                for qc in rec.product_tmpl_id.x_break_qty_price:
                    lines.append((0, 0, {
                        'x_product_qty_pr': qc.x_product_qty,
                        # FIX #1: pass M2O ID, not a record
                        'x_product_uom_pr': qc.x_product_uom.id if qc.x_product_uom else False,
                        'x_product_price_per_uom_pr': qc.x_product_price_per_uom,
                        'x_product_level_price_pr': qc.x_product_price_per_value,
                        # if you also want to seed the "Fixed Price" column on lines:
                        # 'x_product_price_per_value_pr': qc.x_product_price_per_value,
                        # if you have a discount source at template level:
                        # 'x_product_discount_on_level_pr': qc.x_product_discount_on_level,
                    }))

            rec.x_pricelist_break_qty_price = lines

    # @api.onchange('x_pricelist_break_code','product_tmpl_id','price_group_id')
    # def _onchange_pricelist_break_code(self):
    #     res1=[]
    #     for rec in self:
    #         if rec.product_tmpl_id:
    #             # val2={}
    #             # rec.write({'x_pricelist_break_qty_price': [(5, 0, val2)]})
    #             res1=[(5,0,0)]
    #             for qc in rec.product_tmpl_id.x_break_qty_price:
    #                 val = {
    #                 'x_product_qty_pr': qc.x_product_qty,
    #                 'x_product_uom_pr':qc.x_product_uom,
    #                 'x_product_price_per_uom_pr':qc.x_product_price_per_uom,
    #                 'x_product_level_price_pr':qc.x_product_price_per_value,
    #                 }
    #                 res1.append((0,0,val))
    #         if rec.x_pricelist_break_code:
    #             res1=[(5,0,0)]
    #             for qc in rec.x_pricelist_break_code.x_no_of_break_quantities_grid:
    #                 val = {
    #                 'x_product_qty_pr': qc.x_breakqty,
    #                 }
    #                 res1.append((0,0,val))
    #         if rec.price_group_id:
    #             res1=[(5,0,0)]
    #             self.x_pricelist_pricegroup_breakcode = rec.price_group_id.x_qty_break_code
    #             for qc in rec.price_group_id.x_sale_price:
    #                 val = {
    #                 'x_product_qty_pr': qc.x_price_qty,
    #                 }
    #                 res1.append((0,0,val))
    #         rec.x_pricelist_break_qty_price = res1

        #res = super(PricelistItem, self)._onchange_product_tmpl_id()    
        #return res

    # @api.onchange('product_tmpl_id')
    # def _onchange_product_tmpl_id(self):
    #     res1=[]
    #     for rec in self:
    #         if rec.product_tmpl_id:
    #             # val2={}
    #             # rec.write({'x_pricelist_break_qty_price': [(5, 0, val2)]})
    #             res1=[(5,0,0)]
    #             for qc in rec.product_tmpl_id.x_break_qty_price:
    #                 val = {
    #                 'x_product_qty_pr': qc.x_product_qty,
    #                 'x_product_uom_pr':qc.x_product_uom,
    #                 'x_product_price_per_uom_pr':qc.x_product_price_per_uom,
    #                 'x_product_price_per_value_pr':qc.x_product_price_per_value,
    #                 }
    #                 res1.append((0,0,val))
    #         rec.x_pricelist_break_qty_price = res1
    #     res = super(PricelistItem, self)._onchange_product_tmpl_id()    
    #     return res

class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    x_Vendor_FSC = fields.Selection([
        ('not', 'NOT FSC'),
        ('fscmix', 'FSC MIX'),
        ('fscrecycled', 'FSC RECYCLED'),
        ('fscrecycled100', 'FSC RECYCLED 100 PERCENT'),
        ], 'Vendor FSC')
    x_product_convert_from_pur_uom = fields.Float('Convert from Purchased UoM',digits='EF Price')
    x_product_convert_to_sku = fields.Float('Convert to SKU',digits='EF Price')

class ProductEmbosser(models.Model):
    _name = "product.embosser"

    x_mrp_embosser = fields.Many2one('mrp.workcenter','Embosser', domain=([('x_embosser','=','True')]))
    x_product_embosser = fields.Many2one('product.template','Embossers')
    x_product_product_embosser = fields.Many2one('product.product','Embossers')
