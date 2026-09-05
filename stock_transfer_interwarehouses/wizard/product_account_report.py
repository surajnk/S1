from odoo import models, fields, api


class ProductAccountReport(models.TransientModel):
    _name = 'product.report.wizard'

    start_date = fields.Date(string='Date')
    end_date = fields.Date(string='End Date')
    warehouse_id = fields.Many2one('stock.warehouse', string="Warehouse", required=True)
    item_id = fields.Many2one('product.item.group', string="Item Group")
    product_ids = fields.Many2many("product.product", string="Products")
    skip_nonavailable = fields.Boolean(string='Skip Zero Qty')

    def product_report_xlsx(self):
        domain = []
        product_list = []
        if self.product_ids:
            domain += [('id', 'in', self.product_ids.ids)]
        if self.item_id:
            domain += [('x_product_item', '=', self.item_id.id)]
        if self.skip_nonavailable:  # Check if the boolean field is True
            domain += [('qty_available', '>', 0)]

        product_ids = self.env['product.product'].search(domain)
        for item in product_ids:
            val = {
                'account': str(item.asset_category_id.account_asset_id.code) + " " + str(
                    item.asset_category_id.account_asset_id.name),
                'description': item.default_code + "-" + item.name,
                'quantity': item.with_context(
                    {'warehouse': self.warehouse_id.id, 'to_date': self.start_date}).qty_available,
                'unit_price': item.standard_price,
                'Value': item.with_context({'warehouse': self.warehouse_id.id,
                                            'to_date': self.start_date}).qty_available * item.standard_price
            }
            product_list.append(val)

        data = {
            'product': product_list,
            'date': self.start_date
        }
        return self.env.ref('stock_transfer_interwarehouses.product_xlsx_report_generate').report_action(self,
                                                                                                         data=data)


class ProductExcelReport(models.AbstractModel):
    _name = 'report.stock_transfer_interwarehouses.generate'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, model):
        sheet = workbook.add_worksheet('Product Report')
        bold = workbook.add_format({'bold': True})
        title = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': 'yellow'})
        sheet.merge_range('A1:E1', 'Ecological Fibers, Inc.', title)
        sheet.merge_range('A2:E2', 'Inventory Report', title)
        sheet.merge_range('A3:E3', data['date'], title)
        sheet.set_column('A:A', 20)
        sheet.set_column('B:B', 20)
        sheet.set_column('C:C', 15)
        sheet.set_column('D:D', 15)
        sheet.set_column('E:E', 15)
        sheet.set_column('F:F', 15)
        sheet.set_column('G:G', 15)
        row = 4
        col = 0
        sheet.write(row, col, 'GL', bold)
        sheet.write(row, col + 1, 'Description', bold)
        sheet.write(row, col + 2, 'Units (yds)', bold)
        sheet.write(row, col + 3, 'Price/Unit ($/yds)', bold)
        sheet.write(row, col + 4, 'Value ($)', bold)
        total = 0
        for item in data['product']:
            row += 1
            sheet.write(row, col, item['account'])
            sheet.write(row, col + 1, item['description'])
            sheet.write(row, col + 2, item['quantity'])
            sheet.write(row, col + 3, item['unit_price'])
            sheet.write(row, col + 4, item['Value'])
            total += item['Value']
        col = 0
        sheet.write(row + 1, col, 'Total', bold)
        sheet.write(row + 1, col + 4, total)
