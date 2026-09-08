from fractions import Fraction

from odoo import models


class MrpWoPackagingReportParser(models.AbstractModel):
    _name = 'report.mrp_wo_packaging_report.report_wo_packaging'
    _description = 'Work Order Packaging Report Parser'

    def _format_fraction(self, value):
        """40.4375 -> '40-7/16"'; 40.0 -> '40"'."""
        if not value:
            return ''
        whole = int(value)
        frac = Fraction(value - whole).limit_denominator(16)
        if not frac:
            return '%d"' % whole
        if whole:
            return '%d-%d/%d"' % (whole, frac.numerator, frac.denominator)
        return '%d/%d"' % (frac.numerator, frac.denominator)

    def _get_putup_size(self, production):
        sale_id = production.procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id
        sale_line = sale_id.order_line[:1] if sale_id else False
        if not sale_line:
            return ''
        parts = [
            self._format_fraction(sale_line.x_customer_order_width),
            self._format_fraction(sale_line.x_customer_order_length),
        ]
        return ' X '.join(part for part in parts if part)

    def _get_report_values(self, docids, data=None):
        wizard = self.env['mrp.wo.packaging.wizard'].browse(docids)
        wizard.ensure_one()
        productions = wizard._get_productions()
        putup_sizes = {production.id: self._get_putup_size(production) for production in productions}
        return {
            'doc_ids': docids,
            'doc_model': 'mrp.wo.packaging.wizard',
            'docs': productions,
            'wizard_date': wizard.date,
            'putup_sizes': putup_sizes,
        }
