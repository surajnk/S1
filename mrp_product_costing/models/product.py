# -*- coding: utf-8 -*-


from odoo import api, models, _
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    _inherit = 'product.product'


    def _compute_bom_price(self, bom, boms_to_recompute=False):
        self.ensure_one()
        if not bom:
            return 0
        if not boms_to_recompute:
            boms_to_recompute = []
        total = costlab = costfixed = byproductamount = 0
        # operations
        for operation in bom.operation_ids:
            costlab += (operation.time_cycle/60) * operation.workcenter_id.costs_hour
            costfixed += (operation.workcenter_id.time_stop + operation.workcenter_id.time_start) * operation.workcenter_id.costs_hour_fixed/60
        total += costlab + costfixed
        # components
        for line in bom.bom_line_ids:
            if line._skip_bom_line(self):
                continue
            if line.child_bom_id and line.child_bom_id in boms_to_recompute:
                child_total = line.product_id._compute_bom_price(line.child_bom_id, boms_to_recompute=boms_to_recompute)
                total += line.product_id.uom_id._compute_price(child_total, line.product_uom_id) * line.product_qty
            else:
                total += line.product_id.uom_id._compute_price(line.product_id.standard_price, line.product_uom_id) * line.product_qty
        # by products
        for byproduct_id in bom.byproduct_ids:
            byproductamount += byproduct_id.product_id.standard_price * byproduct_id.product_qty
        total -= byproductamount
        return bom.product_uom_id._compute_price(total / bom.product_qty, self.uom_id)
