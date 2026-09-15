# -*- coding: utf-8 -*-
from psycopg2.extensions import AsIs

from odoo import api, fields, models, tools


class MrpEmbossingFrameList(models.Model):
    _name = 'mrp.embossing.frame.list'
    _description = 'Embossing Frame List'
    _order = 'frame_number'
    _auto = False

    workorder_id = fields.Many2one('mrp.workorder', string='Work Order', readonly=True)
    workcenter_id = fields.Many2one('mrp.workcenter', string='Work Center', readonly=True)
    frame_number = fields.Integer(string='Fr', readonly=True)
    # Ty / Sl / Status have no source field yet; kept as empty placeholders
    # until those legacy columns are mapped.
    type = fields.Char(string='Ty', readonly=True)
    slot = fields.Char(string='Sl', readonly=True)
    status = fields.Char(string='Status', readonly=True)
    pattern_id = fields.Many2one('product.embossing', string='Pattern', readonly=True)
    production_id = fields.Many2one('mrp.production', string='MO Number', readonly=True)
    sale_id = fields.Many2one('sale.order', string='SO Number', readonly=True)
    date_planned_start_wo = fields.Datetime(string='Scheduled Start', readonly=True)

    def _select(self):
        return """
            SELECT
                wo.id AS id,
                wo.id AS workorder_id,
                wc.id AS workcenter_id,
                wc.x_frame_wc_number AS frame_number,
                NULL::varchar AS type,
                NULL::varchar AS slot,
                NULL::varchar AS status,
                wo.x_pattern_wo AS pattern_id,
                mp.id AS production_id,
                so.id AS sale_id,
                wo.date_planned_start_wo AS date_planned_start_wo
        """

    def _from(self):
        return """
            mrp_workorder wo
            JOIN mrp_workcenter wc ON wc.id = wo.workcenter_id
            LEFT JOIN mrp_production mp ON mp.id = wo.production_id
            LEFT JOIN sale_order so ON so.name = mp.origin
        """

    def _where(self):
        return """
            WHERE wo.state NOT IN ('done', 'cancel')
            AND wc.x_frame_wc_number IS NOT NULL
        """

    @api.model
    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS ( %s FROM %s %s )",
            (
                AsIs(self._table),
                AsIs(self._select()),
                AsIs(self._from()),
                AsIs(self._where()),
            ),
        )
