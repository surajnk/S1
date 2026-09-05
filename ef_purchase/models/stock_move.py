from odoo import api, fields, models, tools, _
import logging
import math

_logger = logging.getLogger(__name__)


class StockMove(models.Model):
    _inherit = 'stock.move'

    is_convert_ibs_yrd = fields.Boolean("Is Convert Ibs to Yard",store=True)

    po_line_product_qty = fields.Float(
        related='purchase_line_id.product_qty',
        string='PO Line Qty',
        readonly=True,
    )
    po_line_product_uom = fields.Many2one(
        related='purchase_line_id.product_uom',
        string='PO Line UoM',
        readonly=True,
    )

    po_line_qty_received = fields.Float(
        related='purchase_line_id.qty_received',
        string='Received(PO UoM)',
        readonly=True,
    )

    current_receipt_qty_ibs = fields.Float(
        string='Current Receipt Qty (PO UoM)',
        compute='_compute_current_receipt_qty_ibs',
    )

    @api.depends('move_line_ids.qty_in_ibs', 'move_line_nosuggest_ids.qty_in_ibs', 'picking_type_id')
    def _compute_current_receipt_qty_ibs(self):
        for move in self:
            move.current_receipt_qty_ibs = sum(move._get_move_lines().mapped('qty_in_ibs'))
                


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    qty_in_ibs = fields.Float(" Qty Rcvd")
    is_convert_ibs_yrd = fields.Boolean(related='move_id.is_convert_ibs_yrd', store=True)

    @api.onchange('qty_in_ibs')
    def onchange_update_done_qty(self):
        """
        """
        for rec in self:
            if self.qty_in_ibs:
                move = rec.move_id
                for product_supplier in move.product_id.seller_ids:
                    _logger.info("TESTT")
                    if product_supplier.name.id == move.picking_id.partner_id.id or product_supplier.name.id == move.picking_id.partner_id.parent_id.id:
                        if product_supplier.x_product_convert_from_pur_uom > 0.0 and move.picking_id.move_ids_without_package.purchase_line_id.product_uom.factor_inv > 0.0:
                            _logger.info("TESTTTTT1111")
                            self.qty_done = math.ceil(self.qty_in_ibs * (product_supplier.x_product_convert_to_sku / product_supplier.x_product_convert_from_pur_uom))
                            # self.qty_done = math.ceil((product_supplier.x_product_convert_to_sku * (
                            #         self.qty_in_ibs / move.picking_id.move_ids_without_package.purchase_line_id.product_uom.factor_inv)) / \
                            #                 product_supplier.x_product_convert_from_pur_uom)
            else:
                self.qty_done = 0
# from odoo import api, fields, models, tools, _
# import logging
# import math

# _logger = logging.getLogger(__name__)


# class StockMove(models.Model):
#     _inherit = 'stock.move'

#     is_convert_ibs_yrd = fields.Boolean("Is Convert Ibs to Yard",store=True)


# class StockMoveLine(models.Model):
#     _inherit = 'stock.move.line'

#     qty_in_ibs = fields.Float("Quantity in Ibs")
#     is_convert_ibs_yrd = fields.Boolean(related='move_id.is_convert_ibs_yrd', store=True)

#     @api.onchange('qty_in_ibs')
#     def onchange_update_done_qty(self):
#         """
#         """
#         for rec in self:
#             if self.qty_in_ibs:
#                 move = rec.move_id
#                 for product_supplier in move.product_id.seller_ids:
#                     _logger.info("TESTT")
#                     if product_supplier.name.id == move.picking_id.partner_id.id or product_supplier.name.id == move.picking_id.partner_id.parent_id.id:
#                         if product_supplier.x_product_convert_from_pur_uom > 0.0 and move.picking_id.move_ids_without_package.purchase_line_id.product_uom.factor_inv > 0.0:
#                             _logger.info("TESTTTTT1111")
#                             self.qty_done = math.ceil(self.qty_in_ibs * (product_supplier.x_product_convert_to_sku / product_supplier.x_product_convert_from_pur_uom))
#                             # self.qty_done = math.ceil((product_supplier.x_product_convert_to_sku * (
#                             #         self.qty_in_ibs / move.picking_id.move_ids_without_package.purchase_line_id.product_uom.factor_inv)) / \
#                             #                 product_supplier.x_product_convert_from_pur_uom)
#             else:
#                 self.qty_done = 0
