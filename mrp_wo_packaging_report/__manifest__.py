{
    'name': 'MRP Work Order Packaging Report',
    'version': '14.0.1.0.0',
    'summary': 'Work Order / packaging slip report generated via a delivery-date wizard',
    'category': 'Manufacturing',
    'author': 'ATC ONLINE LLP',
    'depends': ['mrp_mto_analytic', 'ef_sales', 'ef_product'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/mrp_wo_packaging_wizard_view.xml',
        'report/mrp_wo_packaging_paperformat.xml',
        'report/mrp_wo_packaging_report.xml',
        'report/mrp_wo_packaging_report_actions.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
