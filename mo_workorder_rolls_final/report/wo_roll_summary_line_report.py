from odoo import api, models

class WoRollSummaryLineReport(models.AbstractModel):
    _name = 'report.mo_workorder_rolls_final.wo_roll_summary_line_document'
    _description = 'Workorder Roll Summary Line Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['wo.roll.summary.wizard'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'wo.roll.summary.wizard',
            'docs': docs,
        }
