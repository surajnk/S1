from odoo import _, fields, models, api


class GetSettlementInvoice(models.TransientModel):
    _name = "get.settlement.invoice"
    _description = "Get Settlement Invoice"

    settlement_invoice_ids = fields.One2many('get.settlement.invoice.line', 'get_settlement_invoice_id', 'Settlement Invoice Lines')

    def settlement_invoice(self):
        move_obj = self.env['account.move'].browse(self._context.get('active_ids'))
        move_lines = []
        for line in self.settlement_invoice_ids:
            move_lines.append((0, 0, {
                'name': 'Settlement from ' + str(line.move_id.name),
                'quantity': 1,
                'price_unit': -line.amount,
                'account_id': move_obj.partner_id.property_account_payable_id.id,
                #'account_id': move_obj.invoice_line_ids[0].product_id.categ_id.property_account_income_categ_id.id,
            }))
            move_obj.invoice_line_ids = move_lines
            line.move_id.remaining_commission_total -= line.amount


class GetSettlementInvoiceLine(models.TransientModel):
    _name = "get.settlement.invoice.line"
    _description = "Get Settlement Invoice Line"

    get_settlement_invoice_id = fields.Many2one('get.settlement.invoice', 'Settlement Invoice')
    move_id = fields.Many2one('account.move', 'Bill', domain=[('remaining_commission_total', '>', 0)])
    remaining_commission_total = fields.Float('Remaining Commission')
    amount = fields.Float('Amount')

    @api.onchange('move_id')
    def onchange_move_id(self):
        if self.move_id:
            self.remaining_commission_total = self.move_id.remaining_commission_total
