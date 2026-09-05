{
    'name': 'Shipping Manifest Report',
    'version': '14.0.1.0.0',
    'summary': 'Shipping Manifest report generated via a date-picker wizard',
    'category': 'Inventory',
    'author': 'ATC ONLINE LLP',
    'depends': ['stock', 'sale', 'ef_stock'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/shipping_manifest_wizard_view.xml',
        'report/shipping_manifest_report.xml',
        'report/shipping_manifest_paperformat.xml',
        'report/shipping_manifest_report_actions.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
