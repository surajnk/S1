# -*- coding: utf-8 -*-

import json
import logging

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.main import ReportController

_logger = logging.getLogger(__name__)

SAMPLE_PRINT_REPORT = 'ef_sales.report_sales_custom'


class SampleReportController(ReportController):

    @http.route()
    def report_download(self, data, token, context=None):
        response = super().report_download(data, token, context=context)
        # TEMPORARY diagnostics (warning level so it shows even with log_level=warn)
        _logger.warning("SamplePrinted diag: report_download called, status=%s, data=%s",
                        getattr(response, 'status_code', None), data)
        try:
            self._mark_sample_printed(data, response)
        except Exception:
            # Never break the user's download because of the tracking flag
            _logger.exception("Sample Printed tracking failed")
        return response

    def _mark_sample_printed(self, data, response):
        """Move sample orders to Sample Printed status when the SALES ORDER report is
        downloaded from the Print menu."""
        if response.status_code != 200:
            return
        url, report_type = json.loads(data)[:2]
        if report_type != 'qweb-pdf':
            return
        parts = url.split('/report/pdf/')[1].split('?')[0].split('/')
        _logger.debug("Report download: %s", parts)
        if parts[0] != SAMPLE_PRINT_REPORT or len(parts) < 2:
            return
        ids = [int(i) for i in parts[1].split(',')]
        # sudo: users who can print an order may not have write access on it
        orders = request.env['sale.order'].sudo().browse(ids).filtered(
            lambda o: o.x_is_sample and o.state not in ('sample_printed', 'closed', 'cancel'))
        _logger.info("Sample Printed: marking orders %s", orders.ids)
        orders.write({'x_sample_printed': True, 'state': 'sample_printed'})
