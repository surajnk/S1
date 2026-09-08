from odoo import models


class MrpWoPackagingReportParser(models.AbstractModel):
    _name = 'report.mrp_wo_packaging_report.report_wo_packaging'
    _description = 'Work Order Packaging Report Parser'

    def _get_report_values(self, docids, data=None):
        wizard = self.env['mrp.wo.packaging.wizard'].browse(docids)
        wizard.ensure_one()
        productions = wizard._get_productions()
        return {
            'doc_ids': docids,
            'doc_model': 'mrp.wo.packaging.wizard',
            'docs': productions,
            'wizard_date': wizard.date,
        }
