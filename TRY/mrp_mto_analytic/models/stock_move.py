# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account')
    origin = fields.Char(readonly=True)


class StockMove(models.Model):
    _inherit = 'stock.move'

    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')


    # stock module
    def _prepare_procurement_values(self):
        values = super()._prepare_procurement_values()
        values.update({'account_analytic_id': self.group_id.sale_id.analytic_account_id.id})
        return values

    # stock_account module
    def _prepare_account_move_line(self, qty, cost, credit_account_id, debit_account_id, description):
        self.ensure_one()
        res = super()._prepare_account_move_line(qty, cost, credit_account_id, debit_account_id, description)
        analytic_account = self.analytic_account_id.id or self.picking_id.analytic_account_id.id
        if not analytic_account or not res:
            return res
        for num in range(0, 2):
            if res[num][2]["account_id"] != self.product_id.categ_id.property_stock_valuation_account_id.id:
                res[num][2].update({'analytic_account_id': analytic_account})
        return res


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    analytic_account_id = fields.Many2one('account.analytic.account', 'Analytic Account', related='move_id.analytic_account_id')