{
    'name': 'Sales Extension - EF',
    'summary': """
        Sale Extension - EF 
        """,
    'description': """
        Sale Extension - EF

        Version 14.0.0.1 - Quotation/Sale Order Modifications.
    """,
    'category': 'Sale',
    'author': 'ATC ONLINE LLP',
    'company': 'ATC ONLINE LLP',
    'maintainer': 'Suraj',
    'version': '14.0.0.1',
    'depends': ['sale_management', 'ef_product', 'web_domain_field'],
    'data': [
        'security/ir.model.access.csv',
        'security/security_view.xml',
        'report/report.xml',
        'report/price_quotation_report.xml',
        'views/ef_sale_view.xml',
        'data/sale_mail_custom_template.xml',
        'wizard/sale_order_report_wizard.xml',
        'report/sales_by_sales_person_report.xml',
        'report/sales_by_customer.xml',
        'report/sale_by_sale_customer_gl.xml',
        'report/sale_report_by_account_manager.xml',
        'report/sales_by_ac_gl_report.xml',
        'views/res_config_view.xml'
    ],
    'qweb': [
        'static/xml/colspan.xml'
    ],
    'demo': [

    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
