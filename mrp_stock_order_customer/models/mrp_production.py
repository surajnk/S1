# -*- coding: utf-8 -*-

from odoo import api, models
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _get_stock_order_partner(self):
        self.ensure_one()
        domain = [
            ('name', '=', 'STOCK ORDER'),
            '|',
            ('company_id', '=', False),
            ('company_id', '=', self.company_id.id),
        ]
        partner = self.env['res.partner'].search(domain, limit=1)
        if partner:
            return partner
        return self.env['res.partner'].sudo().create({
            'name': 'STOCK ORDER',
            'company_id': self.company_id.id,
        })

    @api.model_create_multi
    def create(self, vals_list):
        productions = super().create(vals_list)

        for production in productions:
            sale_order = False
            if hasattr(production, '_get_related_sale_order'):
                sale_order = production._get_related_sale_order()

            # Log to see what’s going on
            _logger.info(
                "MO %s created | sale_order=%s | x_customer_name(before)=%s",
                production.name, bool(sale_order), production.x_customer_name.id if production.x_customer_name else False
            )

            if not sale_order and not production.x_customer_name:
                stock_partner = production._get_stock_order_partner()
                # use sudo + write to be safe with access rights and tracking
                production.sudo().write({'x_customer_name': stock_partner.id})

                _logger.info(
                    "MO %s | x_customer_name(after)=%s",
                    production.name, production.x_customer_name.display_name
                )

        return productions
