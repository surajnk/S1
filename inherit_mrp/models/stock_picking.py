from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    mrequest_id = fields.Many2one('project.mrequest', string="Project Request")
    done_mrequest = fields.Boolean(string="Material Request Done")

    def confirm_mrquestt(self):
        result = 0
        for line in self.move_ids_without_package:
            for mline in self.mrequest_id.mrequest_lines:
                if line.product_id == mline.product:
                    if mline.done_quantity < line.product_uom_qty:
                        result += 1
        if result > 0:
            view_id = self.env.ref('inherit_mrp.mrequest_confirm_fom').id
            context = {
                'default_picking_id': self.id,
                'default_mrequest_id': self.mrequest_id.id
            }
            return {
                'type': 'ir.actions.act_window',
                'name': 'Confirm',
                'view_mode': 'tree',
                'view_type': 'form',
                'res_model': 'mrequest.comfirm',
                'view_id': view_id,
                'views': [(view_id, 'form')],
                'target': 'new',
                'context': context
            }
        else:
            self.mrequest_id.state = 'done'
            self.done_mrequest = True

    @api.onchange('move_ids_without_package', 'move_ids_without_package.quantity_done', 'mrequest_id')
    def _onchange_mrequest_id(self):
        for line in self.move_ids_without_package:
            for mline in self.mrequest_id.mrequest_lines:
                if line.product_id.id == mline.product.id:
                    mline.done_quantity = sum(
                        move.quantity_done for move in self.move_ids_without_package
                        if move.product_id.id == mline.product.id
                    )
                    
    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        for line in self.move_ids_without_package:
            if not line.line_check:
                line.line_check = True
                for mline in self.mrequest_id.mrequest_lines:
                    if line.product_id.id == mline.product.id:
                        mline.write({'done_quantity': (mline.done_quantity or 0.0) + line.quantity_done})
        return res

    # def button_validate(self):
    #     res = super(StockPicking, self).button_validate()
    #     for line in self.move_ids_without_package:
    #         if not line.line_check:
    #             line.line_check = True
    #             for mline in self.mrequest_id.mrequest_lines:
    #                  if line.product_id.id == mline.product.id:
    #                         mline.done_quantity += line.quantity_done
    #     return res

    def _action_generate_backorder_wizard(self, show_transfers=False):
        BackorderConfirmation = self.env['stock.backorder.confirmation']
        backorder_wizard = BackorderConfirmation.create({
            'show_transfers': show_transfers,
            'pick_ids': [(4, p.id) for p in self],
        })
        backorder_wizard.process()

class StockMove(models.Model):
    _inherit = 'stock.move'

    line_check = fields.Boolean()