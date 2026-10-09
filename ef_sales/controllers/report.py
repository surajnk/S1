# -*- coding: utf-8 -*-

import json

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import ReportController

SAMPLE_PRINT_REPORT = 'ef_sales.report_sales_custom'


class SampleReportController(ReportController):

    @http.route()
    def report_download(self, data, token, context=None):
        response = super().report_download(data, token, context=context)
        try:
            self._mark_sample_printed(data, response)
        except Exception:
            # Never break the user's download because of the tracking flag
            pass
        return response

    def _mark_sample_printed(self, data, response):
        """Set Sample Printed on sample orders when the SALES ORDER report is
        downloaded from the Print menu."""
        if response.status_code != 200:
            return
        url, report_type = json.loads(data)[:2]
        if report_type != 'qweb-pdf':
            return
        parts = url.split('/report/pdf/')[1].split('?')[0].split('/')
        if parts[0] != SAMPLE_PRINT_REPORT or len(parts) < 2:
            return
        ids = [int(i) for i in parts[1].split(',')]
        # sudo: users who can print an order may not have write access on it
        orders = request.env['sale.order'].sudo().browse(ids).filtered(
            lambda o: o.x_is_sample and not o.x_sample_printed)
        orders.write({'x_sample_printed': True})
