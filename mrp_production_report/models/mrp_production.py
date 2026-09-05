# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
from fractions import Fraction
import logging

_logger = logging.getLogger(__name__)

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    is_printed_mrp_production_report = fields.Boolean(readonly=0, copy=0)

    def print_mrp_production_report(self):
        return self.env.ref('mrp_production_report.action_report_mrp_production').report_action(self)

    def _update_is_printed_mrp_production_report(self):
        if not self.is_printed_mrp_production_report:
            self.is_printed_mrp_production_report = True
        return True

    @api.model
    def get_production_bom_data(self, work_order):
        data_lines = []
        production_rec = work_order.production_id
        _logger.info("MRPPPPPPPPPPP'%s'", production_rec)
        
        for bom_line in production_rec.bom_id.bom_line_ids:
            for workcenter_capacity in bom_line.workcenter_capacities:
                # Filter components for the current work order's workcenter capacities
                bom_components = bom_line.filtered(lambda x: workcenter_capacity in x.workcenter_capacities)
                
                for bom_component in bom_components:
                    # _logger.info("COMPONNENT'%s'", bom_component.product_id.name)
                    data_lines.append({'work_order': workcenter_capacity.name, 'component_name': bom_component.product_id.name})
        _logger.info("DATAA LINESSS'%s'", data_lines)                    
        return data_lines

    @api.model
    def fraction_display(self, value):
        # Check if value is an integer
        if value % 1 == 0:
            return str(int(value))
        # Otherwise, convert to nearest fraction
        frac = Fraction(value).limit_denominator(16)  # Use 16 or adjust for finer precision
        whole = int(frac)
        numerator = frac.numerator - whole * frac.denominator
        denominator = frac.denominator
        if whole > 0 and numerator > 0:
            return f"{whole}-{numerator}/{denominator}"
        elif numerator > 0:
            return f"{numerator}/{denominator}"
        else:
            return str(whole)
    # @api.model
    # def get_production_bom_data(self, work_order):
    #     data_lines = []
    #     production_rec = work_order.production_id
    #     _logger.info("MRPPPPPPPPPPP'%s'",production_rec)
    #     for bo in production_rec.bom_id.bom_line_ids:
    #         bom_component = bo.filtered(lambda x: x.operation_id.id == work_order.operation_id.id)
    #         _logger.info("COMPONNENT'%s'",bom_component.product_id.name)
    #     return {
    #         'component_name': bom_component.product_id.name,
    #     }
