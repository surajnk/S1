from odoo import api, fields, models
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import json


class SleReportWizard(models.TransientModel):
    _name = 'sale.report.wizard'
    _description = 'Report Wizard'

    start_date = fields.Date(string='Start Date', default=fields.Date.today())
    end_date = fields.Date(string='End Date', default=fields.Date.today())
    report_type = fields.Selection([('sp', 'SP'), ('spc', 'SPC'), ('spg', 'SPG'), ('spa', 'SPA'), ('ac', 'AC')],
                                   string="Type")
    user_id = fields.Many2one('res.users', string="Salesperson")
    manager_id = fields.Many2one('res.users', string="Manager")
    is_excel_report = fields.Boolean()

    @api.onchange('report_type')
    def _onchange_report_type(self):
        partne_list = self.env.ref('ef_product.group_sales_rep').users.ids
        partner_mgr_list = self.env.ref('ef_product.group_sales_sup_mgr').users.ids
        listids = partne_list + partner_mgr_list
        domain = {'user_id': [('id', 'in', listids)]}
        mgr_dom = {'manager_id': [('id', 'in', partner_mgr_list)]}
        return {'domain': {**domain, **mgr_dom}, 'value': {'user_id': []}}

    def print_report_excel(self):
        sale_order = self.env['sale.order'].search(
            [('date_order', '>=', self.start_date), ('date_order', '<=', self.end_date)])
        data = {
            'start_date': self.start_date,
            'end_date': self.end_date
            # 'sale': sale_order
        }
        return self.env.ref('ef_sales.xlsx_report_generate_sale').report_action(self, data=data)

    def print_report(self):
        previous_start_date = self.start_date - timedelta(days=365)
        previous_end_date = (self.end_date - relativedelta(years=1)).replace(day=self.end_date.day)
        previous_end_date = previous_end_date.replace(day=1)
        current_year_start_date = self.end_date.replace(month=1, day=1)
        previous_year_start_date = (self.end_date - timedelta(days=365)).replace(month=1, day=1)

        query = """
            SELECT 
                rp.name AS sname,
                SUM(so.amount_total) AS total_amount
            FROM 
                sale_order AS so
            INNER JOIN 
                res_users AS rs ON rs.id = so.user_id 
            INNER JOIN 
                res_partner AS rp ON rp.id = rs.partner_id 
            WHERE 
                so.date_order BETWEEN %s AND %s
            GROUP BY 
                rp.name
            ORDER BY 
                rp.name
        """

        # Fetch current year full report
        self.env.cr.execute(query, (self.start_date, self.end_date))
        current_year_report = self.env.cr.dictfetchall()

        # Fetch current year YTD report
        self.env.cr.execute(query, (current_year_start_date, self.end_date))
        current_ytd_report = self.env.cr.dictfetchall()

        # Fetch previous year full report
        self.env.cr.execute(query, (previous_start_date, previous_end_date))
        previous_year_report = self.env.cr.dictfetchall()

        # Fetch previous year YTD report
        self.env.cr.execute(query, (previous_year_start_date, previous_end_date))
        previous_ytd_report = self.env.cr.dictfetchall()

        # Function to transform list of dicts to dict with name as key
        def list_to_dict(report_list):
            return {item['sname']: item['total_amount'] for item in report_list}

        current_year_report_dict = list_to_dict(current_year_report)
        current_ytd_report_dict = list_to_dict(current_ytd_report)
        previous_year_report_dict = list_to_dict(previous_year_report)
        previous_ytd_report_dict = list_to_dict(previous_ytd_report)

        # Combine results into a list of dictionaries
        combined_report = []
        all_names = set(current_year_report_dict.keys()).union(
            set(current_ytd_report_dict.keys()),
            set(previous_year_report_dict.keys()),
            set(previous_ytd_report_dict.keys())
        )

        for name in all_names:
            combined_report.append({
                'name': name,
                'current_year_total': current_year_report_dict.get(name, 0),
                'current_ytd_total': current_ytd_report_dict.get(name, 0),
                'previous_year_total': previous_year_report_dict.get(name, 0),
                'previous_ytd_total': previous_ytd_report_dict.get(name, 0),
            })

        data = {'combined_report': combined_report, 'formatted_end_date': self.end_date.strftime("%B %Y"),
                'cytd_end_date': 'Ytd ' + self.end_date.strftime("%Y"),
                'prev_end_date': previous_end_date.strftime("%B %Y"),
                'prev_cytd_end_date': 'Ytd ' + previous_end_date.strftime("%Y")}
        return self.env.ref('ef_sales.report_sale_report_wizard2').report_action(None, data=data)

    def print_report_spc(self):
        previous_start_date = self.start_date - timedelta(days=365)
        previous_end_date = (self.end_date - relativedelta(years=1)).replace(day=self.end_date.day)
        previous_end_date = previous_end_date.replace(day=1)
        current_year_start_date = self.end_date.replace(month=1, day=1)
        previous_year_start_date = (self.end_date - timedelta(days=365)).replace(month=1, day=1)

        query = """
            SELECT 
                CASE 
                    WHEN rp.parent_id IS NOT NULL THEN rp_parent.name 
                    ELSE rp.name 
                END AS sname,
                SUM(so.amount_total) AS total_amount
            FROM 
                sale_order AS so
            INNER JOIN 
                res_partner AS rp ON rp.id = so.partner_id 
            LEFT JOIN 
                res_partner AS rp_parent ON rp.parent_id = rp_parent.id
            WHERE 
                so.date_order BETWEEN %s AND %s 
                AND so.user_id = %s
            GROUP BY 
                sname
            ORDER BY 
                sname
        """

        # Fetch current year full report
        self.env.cr.execute(query, (self.start_date, self.end_date, self.user_id.id))
        current_year_report = self.env.cr.dictfetchall()

        # Fetch current year YTD report
        self.env.cr.execute(query, (current_year_start_date, self.end_date, self.user_id.id))
        current_ytd_report = self.env.cr.dictfetchall()

        # Fetch previous year full report
        self.env.cr.execute(query, (previous_start_date, previous_end_date, self.user_id.id))
        previous_year_report = self.env.cr.dictfetchall()

        # Fetch previous year YTD report
        self.env.cr.execute(query, (previous_year_start_date, previous_end_date, self.user_id.id))
        previous_ytd_report = self.env.cr.dictfetchall()

        # Function to transform list of dicts to dict with name as key
        def list_to_dict(report_list):
            return {item['sname']: item['total_amount'] for item in report_list}

        current_year_report_dict = list_to_dict(current_year_report)
        current_ytd_report_dict = list_to_dict(current_ytd_report)
        previous_year_report_dict = list_to_dict(previous_year_report)
        previous_ytd_report_dict = list_to_dict(previous_ytd_report)

        # Combine results into a list of dictionaries
        combined_report = []
        all_names = set(current_year_report_dict.keys()).union(
            set(current_ytd_report_dict.keys()),
            set(previous_year_report_dict.keys()),
            set(previous_ytd_report_dict.keys())
        )

        for name in all_names:
            combined_report.append({
                'name': name,
                'current_year_total': current_year_report_dict.get(name, 0),
                'current_ytd_total': current_ytd_report_dict.get(name, 0),
                'previous_year_total': previous_year_report_dict.get(name, 0),
                'previous_ytd_total': previous_ytd_report_dict.get(name, 0),
            })

        data = {'combined_report': combined_report, 'formatted_end_date': self.end_date.strftime("%B %Y"),
                'salesperson': self.user_id.name,
                'cytd_end_date': 'Ytd ' + self.end_date.strftime("%Y"),
                'prev_end_date': previous_end_date.strftime("%B %Y"),
                'prev_cytd_end_date': 'Ytd ' + previous_end_date.strftime("%Y")}
        return self.env.ref('ef_sales.report_sale_customer').report_action(None, data=data)

    def print_report_spg(self):
        previous_start_date = self.start_date - timedelta(days=365)
        previous_end_date = (self.end_date - relativedelta(years=1)).replace(day=self.end_date.day)
        current_year_start_date = self.end_date.replace(month=1, day=1)
        previous_year_start_date = (self.end_date - timedelta(days=365)).replace(month=1, day=1)

        query = """
            SELECT 
                CASE 
                    WHEN rp.parent_id IS NOT NULL THEN rp_parent.name 
                    ELSE rp.name 
                END AS customer_name,
                pcc."x_Description" AS product_name,
                SUM(sl.price_total) AS total_amount
            FROM 
                sale_order AS so
            INNER JOIN 
                res_partner AS rp ON rp.id = so.partner_id 
            LEFT JOIN 
                res_partner AS rp_parent ON rp.parent_id = rp_parent.id
            INNER JOIN 
                sale_order_line AS sl ON sl.order_id = so.id 
            INNER JOIN 
                product_product AS pp ON sl.product_id = pp.id 
            INNER JOIN 
                product_template AS pt ON pp.product_tmpl_id = pt.id 
            INNER JOIN 
                product_commodity_code AS pcc ON pt.x_class_commodity_group = pcc.id 
            WHERE 
                so.date_order BETWEEN %s AND %s 
                AND so.user_id = %s
            GROUP BY 
                customer_name, pcc."x_Description" 
            ORDER BY 
                customer_name, pcc."x_Description"
        """

        def fetch_report_data(start_date, end_date):
            self.env.cr.execute(query, (start_date, end_date, self.user_id.id))
            return self.env.cr.dictfetchall()

        # Fetching report data for current and previous years
        current_year_report = fetch_report_data(self.start_date, self.end_date)
        current_ytd_report = fetch_report_data(current_year_start_date, self.end_date)
        previous_year_report = fetch_report_data(previous_start_date, previous_end_date)
        previous_ytd_report = fetch_report_data(previous_year_start_date, previous_end_date)

        # Combine results into a list of dictionaries
        combined_report = {}
        for item in current_year_report:
            key = item['customer_name']
            if key not in combined_report:
                combined_report[key] = {
                    'customer': item['customer_name'],
                    'products': []
                }
            combined_report[key]['products'].append({
                'product': item['product_name'],
                'current_year_total': item['total_amount'],
                'current_ytd_total': 0,
                'previous_year_total': 0,
                'previous_ytd_total': 0,
            })

        for item in current_ytd_report:
            key = item['customer_name']
            if key not in combined_report:
                combined_report[key] = {
                    'customer': item['customer_name'],
                    'products': []
                }
            for product in combined_report[key]['products']:
                if product['product'] == item['product_name']:
                    product['current_ytd_total'] = item['total_amount']
                    break
            else:
                combined_report[key]['products'].append({
                    'product': item['product_name'],
                    'current_year_total': 0,
                    'current_ytd_total': item['total_amount'],
                    'previous_year_total': 0,
                    'previous_ytd_total': 0,
                })

        for item in previous_year_report:
            key = item['customer_name']
            if key not in combined_report:
                combined_report[key] = {
                    'customer': item['customer_name'],
                    'products': []
                }
            for product in combined_report[key]['products']:
                if product['product'] == item['product_name']:
                    product['previous_year_total'] = item['total_amount']
                    break
            else:
                combined_report[key]['products'].append({
                    'product': item['product_name'],
                    'current_year_total': 0,
                    'current_ytd_total': 0,
                    'previous_year_total': item['total_amount'],
                    'previous_ytd_total': 0,
                })

        for item in previous_ytd_report:
            key = item['customer_name']
            if key not in combined_report:
                combined_report[key] = {
                    'customer': item['customer_name'],
                    'products': []
                }
            for product in combined_report[key]['products']:
                if product['product'] == item['product_name']:
                    product['previous_ytd_total'] = item['total_amount']
                    break
            else:
                combined_report[key]['products'].append({
                    'product': item['product_name'],
                    'current_year_total': 0,
                    'current_ytd_total': 0,
                    'previous_year_total': 0,
                    'previous_ytd_total': item['total_amount'],
                })

        combined_report_list = [{'customer': customer, 'products': details['products']} for customer, details in
                                combined_report.items()]

        data = {
            'combined_report': combined_report_list,
            'formatted_end_date': self.end_date.strftime("%B %Y"),
            'salesperson': self.user_id.name,
            'cytd_end_date': 'Ytd ' + self.end_date.strftime("%Y"),
            'prev_end_date': previous_end_date.strftime("%B %Y"),
            'prev_cytd_end_date': 'Ytd ' + previous_end_date.strftime("%Y")
        }
        return self.env.ref('ef_sales.report_sale_customer_gl').report_action(None, data=data)

    # def print_report_spg(self):
    #     previous_start_date = self.start_date - timedelta(days=365)
    #     previous_end_date = (self.end_date - relativedelta(years=1)).replace(day=self.end_date.day)
    #     current_year_start_date = self.end_date.replace(month=1, day=1)
    #     previous_year_start_date = (self.end_date - timedelta(days=365)).replace(month=1, day=1)
    #
    #     query = """
    #         SELECT
    #             rp.name AS customer_name,
    #             pt.x_class_commodity_group  AS product_name,
    #             SUM(sl.price_total) AS total_amount
    #         FROM
    #             sale_order AS so
    #         INNER JOIN
    #             res_partner AS rp ON rp.id = so.partner_id
    #         INNER JOIN
    #             sale_order_line AS sl ON sl.order_id = so.id
    #         INNER JOIN
    #             product_product AS pp ON sl.product_id = pp.id
    #         INNER JOIN
    #             product_template AS pt ON pp.product_tmpl_id = pt.id
    #          INNER JOIN
    #             product_commodity_code AS pcc ON pt.x_class_commodity_group = pcc.id
    #         WHERE
    #             so.date_order BETWEEN %s AND %s
    #             AND so.user_id = %s
    #         GROUP BY
    #             rp.name, pt.x_class_commodity_group
    #         ORDER BY
    #             rp.name, pt.x_class_commodity_group
    #     """
    #
    #     def fetch_report_data(start_date, end_date):
    #         self.env.cr.execute(query, (start_date, end_date, self.user_id.id))
    #         return self.env.cr.dictfetchall()
    #
    #     # Fetching report data for current and previous years
    #     current_year_report = fetch_report_data(self.start_date, self.end_date)
    #     current_ytd_report = fetch_report_data(current_year_start_date, self.end_date)
    #     previous_year_report = fetch_report_data(previous_start_date, previous_end_date)
    #     previous_ytd_report = fetch_report_data(previous_year_start_date, previous_end_date)
    #
    #     # Combine results into a list of dictionaries
    #     combined_report = {}
    #     for item in current_year_report:
    #         key = item['customer_name']
    #         if key not in combined_report:
    #             combined_report[key] = {
    #                 'customer': item['customer_name'],
    #                 'products': []
    #             }
    #         combined_report[key]['products'].append({
    #             'product': item['product_name'],
    #             'current_year_total': item['total_amount'],
    #             'current_ytd_total': 0,
    #             'previous_year_total': 0,
    #             'previous_ytd_total': 0,
    #         })
    #
    #     for item in current_ytd_report:
    #         key = item['customer_name']
    #         for product in combined_report[key]['products']:
    #             if product['product'] == item['product_name']:
    #                 product['current_ytd_total'] = item['total_amount']
    #                 break
    #         else:
    #             combined_report[key]['products'].append({
    #                 'product': item['product_name'],
    #                 'current_year_total': 0,
    #                 'current_ytd_total': item['total_amount'],
    #                 'previous_year_total': 0,
    #                 'previous_ytd_total': 0,
    #             })
    #
    #     for item in previous_year_report:
    #         key = item['customer_name']
    #         for product in combined_report[key]['products']:
    #             if product['product'] == item['product_name']:
    #                 product['previous_year_total'] = item['total_amount']
    #                 break
    #         else:
    #             combined_report[key]['products'].append({
    #                 'product': item['product_name'],
    #                 'current_year_total': 0,
    #                 'current_ytd_total': 0,
    #                 'previous_year_total': item['total_amount'],
    #                 'previous_ytd_total': 0,
    #             })
    #
    #     for item in previous_ytd_report:
    #         key = item['customer_name']
    #         for product in combined_report[key]['products']:
    #             if product['product'] == item['product_name']:
    #                 product['previous_ytd_total'] = item['total_amount']
    #                 break
    #         else:
    #             combined_report[key]['products'].append({
    #                 'product': item['product_name'],
    #                 'current_year_total': 0,
    #                 'current_ytd_total': 0,
    #                 'previous_year_total': 0,
    #                 'previous_ytd_total': item['total_amount'],
    #             })
    #
    #     combined_report_list = [{'customer': customer, 'products': details['products']} for customer, details in
    #                             combined_report.items()]
    #
    #     data = {
    #         'combined_report': combined_report_list,
    #         'formatted_end_date': self.end_date.strftime("%B %Y"),
    #         'salesperson': self.user_id.name,
    #         'cytd_end_date': 'Ytd ' + self.end_date.strftime("%Y"),
    #         'prev_end_date': previous_end_date.strftime("%B %Y"),
    #         'prev_cytd_end_date': 'Ytd ' + previous_end_date.strftime("%Y")
    #     }
    #     return self.env.ref('ef_sales.report_sale_customer_gl').report_action(None, data=data)

    # def print_report_spa(self):
    #     previous_start_date = self.start_date - timedelta(days=365)
    #     previous_end_date = (self.end_date - relativedelta(years=1)).replace(day=self.end_date.day)
    #     current_year_start_date = self.end_date.replace(month=1, day=1)
    #     previous_year_start_date = (self.end_date - timedelta(days=365)).replace(month=1, day=1)
    #
    #     query = """
    #         SELECT
    #             rss.id AS salesperson,
    #             rp.name AS customer_name,
    #              pcc."x_Description" AS product_name,
    #             SUM(sl.price_total) AS total_amount
    #         FROM
    #             sale_order AS so
    #         INNER JOIN
    #             res_partner AS rp ON rp.id = so.partner_id
    #         INNER JOIN
    #             res_users AS rs ON rs.id = rp.x_manager
    #         LEFT JOIN
    #             res_users AS rss ON rss.id = rp.user_id
    #         INNER JOIN
    #             sale_order_line AS sl ON sl.order_id = so.id
    #         INNER JOIN
    #             product_product AS pp ON sl.product_id = pp.id
    #         INNER JOIN
    #             product_template AS pt ON pp.product_tmpl_id = pt.id
    #          INNER JOIN
    #             product_commodity_code AS pcc ON pt.x_class_commodity_group = pcc.id
    #         WHERE
    #             so.date_order BETWEEN %s AND %s
    #             AND rp.x_manager = %s
    #         GROUP BY
    #             rss.id, rp.name,  pcc."x_Description"
    #         ORDER BY
    #             rss.id, rp.name,  pcc."x_Description"
    #     """
    #
    #     def fetch_report_data(start_date, end_date):
    #         self.env.cr.execute(query, (start_date, end_date, self.manager_id.id))
    #         return self.env.cr.dictfetchall()
    #
    #     # Fetching report data for current and previous years
    #     current_year_report = fetch_report_data(self.start_date, self.end_date)
    #     current_ytd_report = fetch_report_data(current_year_start_date, self.end_date)
    #     previous_year_report = fetch_report_data(previous_start_date, previous_end_date)
    #     previous_ytd_report = fetch_report_data(previous_year_start_date, previous_end_date)
    #
    #     # Combine results into a list of dictionaries
    #     combined_report = {}
    #     for item in current_year_report:
    #         sp_key = item['salesperson']
    #         if sp_key not in combined_report:
    #             combined_report[sp_key] = {'salesperson': sp_key, 'data': {}}
    #
    #         key = item['customer_name']
    #         if key not in combined_report[sp_key]['data']:
    #             combined_report[sp_key]['data'][key] = {
    #                 'customer': item['customer_name'],
    #                 'products': []
    #             }
    #         combined_report[sp_key]['data'][key]['products'].append({
    #             'product': item['product_name'],
    #             'current_year_total': item['total_amount'],
    #             'current_ytd_total': 0,
    #             'previous_year_total': 0,
    #             'previous_ytd_total': 0,
    #         })
    #
    #     for item in current_ytd_report:
    #         sp_key = item['salesperson']
    #         key = item['customer_name']
    #         for product in combined_report[sp_key]['data'][key]['products']:
    #             if product['product'] == item['product_name']:
    #                 product['current_ytd_total'] = item['total_amount']
    #                 break
    #         else:
    #             combined_report[sp_key]['data'][key]['products'].append({
    #                 'product': item['product_name'],
    #                 'current_year_total': 0,
    #                 'current_ytd_total': item['total_amount'],
    #                 'previous_year_total': 0,
    #                 'previous_ytd_total': 0,
    #             })
    #
    #     for item in previous_year_report:
    #         sp_key = item['salesperson']
    #         key = item['customer_name']
    #         for product in combined_report[sp_key]['data'][key]['products']:
    #             if product['product'] == item['product_name']:
    #                 product['previous_year_total'] = item['total_amount']
    #                 break
    #         else:
    #             combined_report[sp_key]['data'][key]['products'].append({
    #                 'product': item['product_name'],
    #                 'current_year_total': 0,
    #                 'current_ytd_total': 0,
    #                 'previous_year_total': item['total_amount'],
    #                 'previous_ytd_total': 0,
    #             })
    #
    #     for item in previous_ytd_report:
    #         sp_key = item['salesperson']
    #         key = item['customer_name']
    #         for product in combined_report[sp_key]['data'][key]['products']:
    #             if product['product'] == item['product_name']:
    #                 product['previous_ytd_total'] = item['total_amount']
    #                 break
    #         else:
    #             combined_report[sp_key]['data'][key]['products'].append({
    #                 'product': item['product_name'],
    #                 'current_year_total': 0,
    #                 'current_ytd_total': 0,
    #                 'previous_year_total': 0,
    #                 'previous_ytd_total': item['total_amount'],
    #             })
    #
    #     combined_report_list = []
    #     for salesperson, details in combined_report.items():
    #         data_list = [{'customer': customer, 'products': products['products']} for customer, products in
    #                      details['data'].items()]
    #         sp = self.env['res.users'].search([('id', '=', salesperson)]).name
    #         combined_report_list.append({'salesperson': sp, 'data': data_list})
    #
    #
    #     data = {
    #         'combined_report': combined_report_list,
    #         'formatted_end_date': self.end_date.strftime("%B %Y"),
    #         'salesperson': self.manager_id.name,
    #         'cytd_end_date': 'Ytd ' + self.end_date.strftime("%Y"),
    #         'prev_end_date': previous_end_date.strftime("%B %Y"),
    #         'prev_cytd_end_date': 'Ytd ' + previous_end_date.strftime("%Y")
    #     }
    #
    #     return self.env.ref('ef_sales.report_sale_customer_gl_ac').report_action(None, data=data)
    def print_report_spa(self):
        previous_start_date = self.start_date - timedelta(days=365)
        previous_end_date = (self.end_date - relativedelta(years=1)).replace(day=self.end_date.day)
        current_year_start_date = self.end_date.replace(month=1, day=1)
        previous_year_start_date = (self.end_date - timedelta(days=365)).replace(month=1, day=1)

        query = """
            SELECT
                rss.id AS salesperson,
                CASE 
                    WHEN rp.parent_id IS NOT NULL THEN rp_parent.name 
                    ELSE rp.name 
                END AS customer_name,
                pcc."x_Description" AS product_name,
                SUM(sl.price_total) AS total_amount
            FROM
                sale_order AS so
            INNER JOIN
                res_partner AS rp ON rp.id = so.partner_id
            LEFT JOIN 
                res_partner AS rp_parent ON rp.parent_id = rp_parent.id
            INNER JOIN
                res_users AS rs ON rs.id = rp.x_manager
            LEFT JOIN
                res_users AS rss ON rss.id = rp.user_id
            INNER JOIN
                sale_order_line AS sl ON sl.order_id = so.id
            INNER JOIN
                product_product AS pp ON sl.product_id = pp.id
            INNER JOIN
                product_template AS pt ON pp.product_tmpl_id = pt.id
            INNER JOIN 
                product_commodity_code AS pcc ON pt.x_class_commodity_group = pcc.id 
            WHERE
                so.date_order BETWEEN %s AND %s
                AND rp.x_manager = %s
            GROUP BY
                rss.id, customer_name, pcc."x_Description"
            ORDER BY
                rss.id, customer_name, pcc."x_Description"
        """

        def fetch_report_data(start_date, end_date):
            self.env.cr.execute(query, (start_date, end_date, self.manager_id.id))
            return self.env.cr.dictfetchall()

        # Fetching report data for current and previous years
        current_year_report = fetch_report_data(self.start_date, self.end_date)
        current_ytd_report = fetch_report_data(current_year_start_date, self.end_date)
        previous_year_report = fetch_report_data(previous_start_date, previous_end_date)
        previous_ytd_report = fetch_report_data(previous_year_start_date, previous_end_date)

        # Combine results into a list of dictionaries
        combined_report = {}

        def initialize_combined_report_item(sp_key, customer_name):
            if sp_key not in combined_report:
                combined_report[sp_key] = {'salesperson': sp_key, 'data': {}}
            if customer_name not in combined_report[sp_key]['data']:
                combined_report[sp_key]['data'][customer_name] = {
                    'customer': customer_name,
                    'products': []
                }

        for item in current_year_report:
            sp_key = item['salesperson']
            key = item['customer_name']
            initialize_combined_report_item(sp_key, key)
            combined_report[sp_key]['data'][key]['products'].append({
                'product': item['product_name'],
                'current_year_total': item['total_amount'],
                'current_ytd_total': 0,
                'previous_year_total': 0,
                'previous_ytd_total': 0,
            })

        for item in current_ytd_report:
            sp_key = item['salesperson']
            key = item['customer_name']
            initialize_combined_report_item(sp_key, key)
            for product in combined_report[sp_key]['data'][key]['products']:
                if product['product'] == item['product_name']:
                    product['current_ytd_total'] = item['total_amount']
                    break
            else:
                combined_report[sp_key]['data'][key]['products'].append({
                    'product': item['product_name'],
                    'current_year_total': 0,
                    'current_ytd_total': item['total_amount'],
                    'previous_year_total': 0,
                    'previous_ytd_total': 0,
                })

        for item in previous_year_report:
            sp_key = item['salesperson']
            key = item['customer_name']
            initialize_combined_report_item(sp_key, key)
            for product in combined_report[sp_key]['data'][key]['products']:
                if product['product'] == item['product_name']:
                    product['previous_year_total'] = item['total_amount']
                    break
            else:
                combined_report[sp_key]['data'][key]['products'].append({
                    'product': item['product_name'],
                    'current_year_total': 0,
                    'current_ytd_total': 0,
                    'previous_year_total': item['total_amount'],
                    'previous_ytd_total': 0,
                })

        for item in previous_ytd_report:
            sp_key = item['salesperson']
            key = item['customer_name']
            initialize_combined_report_item(sp_key, key)
            for product in combined_report[sp_key]['data'][key]['products']:
                if product['product'] == item['product_name']:
                    product['previous_ytd_total'] = item['total_amount']
                    break
            else:
                combined_report[sp_key]['data'][key]['products'].append({
                    'product': item['product_name'],
                    'current_year_total': 0,
                    'current_ytd_total': 0,
                    'previous_year_total': 0,
                    'previous_ytd_total': item['total_amount'],
                })

        combined_report_list = []
        for salesperson, details in combined_report.items():
            data_list = [{'customer': customer, 'products': products['products']} for customer, products in
                         details['data'].items()]
            sp = self.env['res.users'].search([('id', '=', salesperson)]).name
            combined_report_list.append({'salesperson': sp, 'data': data_list})

        data = {
            'combined_report': combined_report_list,
            'formatted_end_date': self.end_date.strftime("%B %Y"),
            'salesperson': self.manager_id.name,
            'cytd_end_date': 'Ytd ' + self.end_date.strftime("%Y"),
            'prev_end_date': previous_end_date.strftime("%B %Y"),
            'prev_cytd_end_date': 'Ytd ' + previous_end_date.strftime("%Y")
        }

        return self.env.ref('ef_sales.report_sale_customer_gl_ac').report_action(None, data=data)

    def print_report_ac(self):
        previous_start_date = self.start_date - timedelta(days=365)
        previous_end_date = (self.end_date - relativedelta(years=1)).replace(day=self.end_date.day)
        previous_end_date = previous_end_date.replace(day=1)
        current_year_start_date = self.end_date.replace(month=1, day=1)
        previous_year_start_date = (self.end_date - timedelta(days=365)).replace(month=1, day=1)

        query = """
            SELECT 
                rp.name AS sname,
                SUM(so.amount_total) AS total_amount
            FROM 
                sale_order AS so
            INNER JOIN 
                res_partner AS rps ON rps.id = so.partner_id 
            INNER JOIN 
                res_users AS rs ON rs.id = rps.x_manager 
            INNER JOIN 
                res_partner AS rp ON rp.id = rs.partner_id 
            WHERE 
                so.date_order BETWEEN %s AND %s
            GROUP BY 
                rp.name
            ORDER BY 
                rp.name
        """

        # Fetch current year full report
        self.env.cr.execute(query, (self.start_date, self.end_date))
        current_year_report = self.env.cr.dictfetchall()

        # Fetch current year YTD report
        self.env.cr.execute(query, (current_year_start_date, self.end_date))
        current_ytd_report = self.env.cr.dictfetchall()

        # Fetch previous year full report
        self.env.cr.execute(query, (previous_start_date, previous_end_date))
        previous_year_report = self.env.cr.dictfetchall()

        # Fetch previous year YTD report
        self.env.cr.execute(query, (previous_year_start_date, previous_end_date))
        previous_ytd_report = self.env.cr.dictfetchall()

        # Function to transform list of dicts to dict with name as key
        def list_to_dict(report_list):
            return {item['sname']: item['total_amount'] for item in report_list}

        current_year_report_dict = list_to_dict(current_year_report)
        current_ytd_report_dict = list_to_dict(current_ytd_report)
        previous_year_report_dict = list_to_dict(previous_year_report)
        previous_ytd_report_dict = list_to_dict(previous_ytd_report)

        # Combine results into a list of dictionaries
        combined_report = []
        all_names = set(current_year_report_dict.keys()).union(
            set(current_ytd_report_dict.keys()),
            set(previous_year_report_dict.keys()),
            set(previous_ytd_report_dict.keys())
        )

        for name in all_names:
            combined_report.append({
                'name': name,
                'current_year_total': current_year_report_dict.get(name, 0),
                'current_ytd_total': current_ytd_report_dict.get(name, 0),
                'previous_year_total': previous_year_report_dict.get(name, 0),
                'previous_ytd_total': previous_ytd_report_dict.get(name, 0),
            })

        data = {'combined_report': combined_report, 'formatted_end_date': self.end_date.strftime("%B %Y"),
                'cytd_end_date': 'Ytd ' + self.end_date.strftime("%Y"),
                'prev_end_date': previous_end_date.strftime("%B %Y"),
                'prev_cytd_end_date': 'Ytd ' + previous_end_date.strftime("%Y")}
        return self.env.ref('ef_sales.report_sale_by_acoount_mgr').report_action(None, data=data)


class SaleExcelReport(models.AbstractModel):
    _name = 'report.ef_sales.print_sale_report_excel'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, booking):
        sheet = workbook.add_worksheet('Sale Report')
        bold = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        remark = workbook.add_format(
            {'align': 'center', 'valign': 'vcenter', 'border': 1, })
        data_s = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
        total_format = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1, 'bold': True})
        total_amount_format = workbook.add_format(
            {'align': 'right', 'valign': 'vcenter', 'border': 1, 'bold': True})

        sheet.set_column('A:A', 20)
        sheet.set_column('B:B', 15)
        sheet.set_column('C:C', 25)
        sheet.set_column('D:D', 10)
        sheet.set_column('E:E', 10)
        sheet.set_column('F:F', 10)
        sheet.set_column('G:G', 10)
        sheet.set_column('H:H', 10)
        sheet.set_column('I:I', 25)
        sheet.set_column('J:J', 10)
        sheet.set_column('K:K', 10)
        sheet.set_column('L:L', 10)
        sheet.set_column('M:M', 10)
        sheet.set_column('N:N', 10)
        sheet.set_column('O:O', 10)
        sheet.set_column('P:P', 10)
        sheet.set_column('Q:Q', 10)
        sheet.set_column('R:R', 10)
        sheet.set_column('S:S', 10)
        sheet.set_column('T:T', 10)
        sheet.set_column('U:U', 10)
        sheet.set_column('V:V', 10)
        sheet.set_column('X:X', 10)
        sheet.set_column('Y:Y', 10)
        row = 1
        col = 0
        sheet.write(row, col, 'Invoice', bold)
        sheet.write(row, col + 1, 'Inv Date', bold)
        sheet.write(row, col + 2, 'Customer', bold)
        sheet.write(row, col + 3, 'Ref', bold)
        sheet.write(row, col + 4, 'PO#', bold)
        sheet.write(row, col + 5, 'Order', bold)
        sheet.write(row, col + 6, 'Part', bold)
        sheet.write(row, col + 7, 'Size', bold)
        sheet.write(row, col + 8, 'Description', bold)
        sheet.write(row, col + 9, 'Ship Qty', bold)
        sheet.write(row, col + 10, 'Price/Uom', bold)
        sheet.write(row, col + 11, 'Price Uom', bold)
        sheet.write(row, col + 12, 'Line Total', bold)
        sheet.write(row, col + 13, 'Job', bold)
        sheet.write(row, col + 14, 'Title', bold)
        sheet.write(row, col + 15, 'Weight', bold)
        sheet.write(row, col + 16, 'Emboss', bold)
        sheet.write(row, col + 17, 'Invoice $$', bold)
        sheet.write(row, col + 18, 'Wide Yards', bold)
        sheet.write(row, col + 19, 'BOL', bold)
        sheet.write(row, col + 20, 'Bol Weight', bold)
        sale_order = self.env['sale.order'].search(
            [('date_order', '>=', data['start_date']), ('date_order', '<=', data['end_date']),
             ('invoice_ids', '!=', None)])
        for order in sale_order:
            for line in order.invoice_ids:
                row += 1
                col = 0
                # invoice_names = ', '.join(inv.name for inv in order.invoice_ids)
                # invoice_dates = ', '.join(
                #     inv.invoice_date.strftime('%Y-%m-%d') if inv.invoice_date else '' for inv in order.invoice_ids)
                sheet.write(row, col, line.name, data_s)
                sheet.write(row, col + 1, line.invoice_date.strftime('%Y-%m-%d') if line.invoice_date else '', data_s)
                sheet.write(row, col + 2, order.partner_id.parent_id.name if order.partner_id.parent_id else
                order.partner_id.name, data_s)
                sheet.write(row, col + 3, order.partner_id.ref, data_s)
                # po = self.env['purchase.order'].search([('sale_order_id', '=', order.id)])
                sheet.write(row, col + 4, order.client_order_ref if order.client_order_ref else '', data_s)
                sheet.write(row, col + 5, order.name if order else '', data_s)
                size = 0
                for ol in order.order_line:
                    for il in line.invoice_line_ids:
                        if ol.product_id.id == il.product_id.id:
                            if ol.x_customer_order_width and ol.x_customer_order_length:
                                size = str(ol.x_customer_order_width) + '*' + str(ol.x_customer_order_length)
                            else:
                                size = ol.x_customer_order_width
                            x_ref1 = ol.x_ref1
                            x_ref2 = ol.x_ref2
                            x_approx_material_weight = ol.x_approx_material_weight
                            x_order_line_embossing = ol.x_order_line_embossing
                            x_order_master_yards = ol.x_order_master_yards
                            sheet.write(row, col + 6, ol.product_id.name, data_s)

                            sheet.write(row, col + 7, size, data_s)
                            sheet.write(row, col + 8, il.product_id.default_code, data_s)
                            sheet.write(row, col + 9, il.quantity, data_s)
                            sheet.write(row, col + 10, il.price_unit, data_s)
                            sheet.write(row, col + 11, il.product_uom_id.name, data_s)
                            sheet.write(row, col + 12, il.price_total, data_s)
                            sheet.write(row, col + 13, x_ref1 if x_ref1 else '', data_s)
                            sheet.write(row, col + 14, x_ref2 if x_ref2 else '', data_s)
                            sheet.write(row, col + 15, x_approx_material_weight, data_s)
                            sheet.write(row, col + 16, x_order_line_embossing.name, data_s)
                            sheet.write(row, col + 17, il.price_total, data_s)
                            sheet.write(row, col + 18, x_order_master_yards, data_s)
                            sheet.write(row, col + 19, " ", data_s)
                            sheet.write(row, col + 20, " ", data_s)
