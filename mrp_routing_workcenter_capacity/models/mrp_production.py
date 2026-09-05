from odoo import models, api
from odoo.tools import float_round


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    @api.onchange('bom_id', 'product_id', 'product_qty', 'product_uom_id')
    def _onchange_move_raw(self):
        res = super(MrpProduction, self)._onchange_move_raw()
        extra_product = []
        if self.bom_id:
            list_move_raw = []
            for op_rec in self.bom_id.operation_ids:
                for product in op_rec.operation_products_ids:
                    if product and product not in extra_product:
                        extra_product.append(product)
            if extra_product:
                filtered_extra_product = [y.product_id for y in self.move_raw_ids.filtered(lambda x: x.product_id and x.product_id in extra_product)]
                for ex_product in extra_product:
                    if ex_product not in filtered_extra_product:
                        move_dict = self._get_move_raw_values(ex_product, 0, ex_product.uom_id, False, False)
                        if move_dict:
                            list_move_raw.append((0, 0, move_dict))
            self.move_raw_ids = list_move_raw
        return res
