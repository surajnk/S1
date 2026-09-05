from odoo import api, fields, models, _
from odoo.tools import float_compare, float_round


class MrpProductionBackorder(models.TransientModel):
    _inherit = 'mrp.production.backorder'

    warning_message = fields.Text(compute='_compute_warning_message', readonly=True)

    # @api.depends(
    #     'mrp_production_backorder_line_ids.mrp_production_id.qty_produced',
    #     'mrp_production_backorder_line_ids.mrp_production_id.x_order_master_yards',
    #     'mrp_production_backorder_line_ids.mrp_production_id.x_order_mrp_over',
    #     'mrp_production_backorder_line_ids.mrp_production_id.workorder_ids.state',
    # )
    # def _compute_warning_message(self):
    #     for wizard in self:
    #         messages = []
    #         productions = wizard.mrp_production_ids
    #         if not productions:
    #             productions = wizard.mrp_production_backorder_line_ids.mapped('mrp_production_id')
    #         for production in productions:
    #             if not production:
    #                 continue
    #             workorders = production.workorder_ids
    #             if not workorders or any(workorder.state != 'done' for workorder in workorders):
    #                 continue
    #             master_yards = float(production.x_order_master_yards or 0.0)
    #             under_pct = self._parse_over_percentage(production.x_order_mrp_under)
    #             minimum_qty = master_yards * (1 - under_pct / 100.0)
    #             produced_qty = float(production.qty_produced or 0.0)
    #             if minimum_qty <= 0:
    #                 continue
    #             precision = (production.product_uom_id and production.product_uom_id.rounding) or 0.01
    #             if float_compare(produced_qty, minimum_qty, precision_rounding=precision) == -1:
    #                 produced_str = float_round(produced_qty, precision_rounding=precision)
    #                 minimum_str = float_round(minimum_qty, precision_rounding=precision)
    #                 messages.append(_(
    #                     "Produced Quantity (%(produced)s) is less than minimum allowance Quantity (%(minimum)s).",
    #                     produced=produced_str,
    #                     minimum=minimum_str,
    #                 ))
    #         wizard.warning_message = '\n'.join(messages) or False

    # @staticmethod
    # def _parse_over_percentage(value):
    #     value = str(value or '').strip()
    #     if not value:
    #         return 0.0
    #     cleaned = value.replace('%', '').strip()
    #     try:
    #         return float(cleaned)
    #     except ValueError:
    #         return 0.0

    @api.depends(
        'mrp_production_backorder_line_ids.mrp_production_id.qty_produced',
        'mrp_production_backorder_line_ids.mrp_production_id.x_order_master_yards',
        'mrp_production_backorder_line_ids.mrp_production_id.x_order_mrp_under',
        'mrp_production_backorder_line_ids.mrp_production_id.x_order_mrp_over',
        'mrp_production_backorder_line_ids.mrp_production_id.workorder_ids.state',
    )
    def _compute_warning_message(self):
        for wizard in self:
            messages = []
            productions = wizard.mrp_production_ids or wizard.mrp_production_backorder_line_ids.mapped('mrp_production_id')

            for production in productions:
                if not production:
                    continue
                # Require all WOs done for the MO to be validated here
                wos = production.workorder_ids
                if not wos or any(wo.state != 'done' for wo in wos):
                    continue

                master = float(production.x_order_master_yards or 0.0)
                produced = float(production.qty_produced or 0.0)
                if master <= 0:
                    continue

                under_pct = self._parse_percentage(production.x_order_mrp_under)  # e.g., 5 => -5% band
                over_pct  = self._parse_percentage(production.x_order_mrp_over)   # e.g., 7 => +7% band

                # Build the allowed band [min_allowed, max_allowed]
                min_allowed = master * (1 - under_pct / 100.0)
                max_allowed = master * (1 + over_pct  / 100.0)

                precision = (production.product_uom_id and production.product_uom_id.rounding) or 0.01

                # Compare once against the band; emit only if out-of-band
                if float_compare(produced, min_allowed, precision_rounding=precision) == -1:
                    messages.append(_(
                        "[%(mo)s] Produced (%(produced)s) is less than minimum allowed (%(minimum)s).",
                        mo=production.name,
                        produced=float_round(produced, precision_rounding=precision),
                        minimum=float_round(min_allowed, precision_rounding=precision),
                    ))
                elif float_compare(produced, max_allowed, precision_rounding=precision) == 1:
                    messages.append(_(
                        "[%(mo)s] Produced (%(produced)s) exceeds maximum allowed (%(maximum)s).",
                        mo=production.name,
                        produced=float_round(produced, precision_rounding=precision),
                        maximum=float_round(max_allowed, precision_rounding=precision),
                    ))

                # else: inside band → no message

            wizard.warning_message = '\n'.join(messages) or False

    @staticmethod
    def _parse_percentage(value):
        s = str(value or '').strip()
        if not s:
            return 0.0
        s = s.replace('%', '').strip()
        try:
            return float(s)
        except ValueError:
            return
