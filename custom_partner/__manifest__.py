# -*- coding: utf-8 -*-

{
   'name': 'Eco Fibers Inc',
   'version': '14.0',
   'summary': 'Tracking of the Manufacture ,Sales& Purchase records',
   'sequence': 0,
   'author': 'ATC ONLINE LLP',
   'website': 'www.atconline.biz',
   'category': "Tools",
   'company': 'Eco Fibers Inc',
   'description': """ """,
   'depends': ['base','contacts','mail','ef_product','sale_order_line','product','delivery'],
   'data': [
       'security/ir.model.access.csv',
       'security/security_view.xml',
       'views/custom_partner_view.xml',
       'views/sales_offices_view.xml',
       'views/freight_terms_view.xml',
       'views/ship_via_view.xml',
       'views/publisher_view.xml',
       'views/sale_order_view.xml',
       'views/product_product_view.xml',
       'views/product_packaging_view.xml',
       'report/proforma_invoice_report_sale.xml',
       'report/profrma_invoice_report.xml',

       ],

   'demo': [],
   'application': True,
   'installable': True,
   'auto_install': False,
}
