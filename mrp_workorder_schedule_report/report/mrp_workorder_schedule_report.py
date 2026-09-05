from odoo import models

class ReportMrpWorkorderSchedule(models.AbstractModel):
    _name = 'report.mrp_workorder_schedule_report.mrp_workorder_schedule_pdf'
    _description = 'MRP Workorder Schedule PDF'

    def _get_report_values(self, docids, data=None):
        wizard = self.env['mrp.workorder.schedule.wizard'].browse(docids)
        if not wizard:
            # FIX START (replace the corrupted line with these 2 lines)
            active_id = (data or {}).get('active_id') or (data or {}).get('wizard_id') or self.env.context.get('active_id')
            wizard = self.env['mrp.workorder.schedule.wizard'].browse(active_id) if active_id else wizard
            # FIX END
        wizard = wizard[:1]
        if not wizard:
            return {
                'doc_ids': [],
                'doc_model': 'mrp.workorder.schedule.wizard',
                'docs': wizard,
                'data': {},
            }

        report_data = wizard._prepare_report_data()
        return {
            'doc_ids': wizard.ids,
            'doc_model': 'mrp.workorder.schedule.wizard',
            'docs': wizard,
            'data': report_data,
        }
