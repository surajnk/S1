from odoo import fields, models


class ShippingManifestReportParser(models.AbstractModel):
    _name = 'report.shipping_manifest_report.report_manifest'
    _description = 'Shipping Manifest Report Parser'

    def _get_report_values(self, docids, data=None):
        wizard = self.env['shipping.manifest.wizard'].browse(docids)
        wizard.ensure_one()
        report_data = wizard._get_report_data()
        printed_at = fields.Datetime.context_timestamp(
            wizard, fields.Datetime.now()
        )
        return {
            'doc_ids': docids,
            'doc_model': 'shipping.manifest.wizard',
            'docs': wizard,
            'data': {
                'date': wizard.date and wizard.date.strftime('%m/%d/%Y') or '',
                'pending_date': wizard.date and wizard.date.strftime('%b %d, %Y') or '',
                'print_date': printed_at.strftime('%b %d,%Y'),
                'print_time': printed_at.strftime('%H:%M:%S'),
                'shipped_lines': report_data['shipped'],
                'pending_lines': report_data['pending'],
            },
        }