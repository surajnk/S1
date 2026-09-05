{
    'name': 'Invoice Extension - EF',
    'summary': """
        Invoice Extension - EF 
        """,
    'description': """
        Invoice Extension - EF

        Version 14.0.0.1 - Invoice Modifications.
    """,
    'author': 'ATC ONLINE LLP',
    'company': 'ATC ONLINE LLP',
    'maintainer': 'Suraj',
    'version': '14.0.0.1',
    'depends': ['sale_management','ef_product','web_domain_field','ef_sales','account','crm_claim'],
    'data': [

        # 'security/ir.model.access.csv',
        # 'report/report.xml',
        # 'report/price_quotation_report.xml',
        'views/ef_invoice_view.xml',
        # 'data/sale_mail_custom_template.xml',
    ],
    'qweb': [
        # 'static/xml/colspan.xml'
    ],
    'demo': [
        
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
