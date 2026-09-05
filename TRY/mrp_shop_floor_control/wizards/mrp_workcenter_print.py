from odoo import api, fields, models, _
import datetime


class MrpWorkReport(models.TransientModel):
    _name = 'mro.workcenter.report'

    start_date = fields.Datetime('Date', required=1, default=datetime.datetime.today().date())
    end_date = fields.Datetime('Date', required=1, default=datetime.datetime.today().date())
    work_ceter_id = fields.Many2one('mrp.workcenter',required=1, string="Work  Center")

    def print_workorder_report(self):
        wo_query = """
            SELECT DISTINCT
                wo.id AS id,
                wo.name AS name
            FROM
                mrp_workorder AS wo
                
        """

        if self.start_date and self.end_date:
            wo_query += """ WHERE wo.date_planned_start_wo >= '%s' AND wo.date_planned_start_wo <= '%s'""" % (
                self.start_date, self.end_date)
        if self.work_ceter_id:
            wo_query += """ and wo.workcenter_id = '%s'""" % (
                self.work_ceter_id.id)

        self.env.cr.execute(wo_query)
        result = self.env.cr.dictfetchall()
        query = """
        select wo.id as id,wo.name as name,TO_CHAR(t.date_start, 'HH24:MI') as ds,TO_CHAR(t.date_end, 'HH24:MI') AS de,
        FLOOR(t.duration / 60)::TEXT || 'h, ' || (CAST(t.duration AS INTEGER) % 60)::TEXT || 'm' AS d,
        t.x_yards_in as 
        yin,t.x_yards_out as yoout,m.product_id,pt.name as pname ,m.name as mname
        from mrp_workorder as wo
        inner join mrp_workcenter_productivity as t on wo.id = t.workorder_id
        inner join mrp_production as m on m.id = wo.production_id
        inner join product_product as p on p.id = m.product_id
        inner join product_template as pt on p.product_tmpl_id = pt.id
        """
        if self.start_date and self.end_date:
            query += """ where wo.date_planned_start_wo >= '%s' and wo.date_planned_start_wo <= '%s'""" % (
                self.start_date, self.end_date)
        if self.work_ceter_id:
            query += """ and wo.workcenter_id = '%s'""" % (
                self.work_ceter_id.id)
        query += """ ORDER  BY wo.id"""
        self.env.cr.execute(query)
        report = self.env.cr.dictfetchall()
        query_roll = """
                select wo.id as id,wo.name as name,r.quantity as q,rl.name as rname,TO_CHAR(r.date, 'HH24:MI') as date,p.name as uname
                from mrp_workorder as wo
                inner join mrp_wo_roll_line r on wo.id = r.workorder_id
                inner join mrp_production_roll as rl on rl.id = r.roll_id
                inner join res_users as u on u.id = r.user_id
                inner join res_partner as p on p.id = u.partner_id
                """
        if self.start_date and self.end_date:
            query_roll += """ where wo.date_planned_start_wo >= '%s' and wo.date_planned_start_wo <= '%s'""" % (
                self.start_date, self.end_date)
        if self.work_ceter_id:
            query_roll += """ and wo.workcenter_id = '%s'""" % (
                self.work_ceter_id.id)
        query_roll += """ ORDER  BY wo.id"""
        self.env.cr.execute(query_roll)
        report2 = self.env.cr.dictfetchall()

        data = {'mwork': result, 'work': report, 'roll': report2, 'start_date': self.start_date.strftime('%B %d, %Y'),
                'end_date': self.end_date.strftime('%B %d, %Y'),
                'worl': self.work_ceter_id.name
                }
        return self.env.ref('mrp_shop_floor_control.action_mrp_workcenter_report').report_action(None, data=data)
