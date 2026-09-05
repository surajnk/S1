{
    'name': 'Pricelist Mass Level Update',
    'summary': 'Wizard to mass-update Level Price on Quantity Breaks across pricelists',
    'version': '14.0.1.0.0',
    'category': 'Sales',
    'author': 'You',
    'license': 'LGPL-3',
    'depends': ['sale_management'],
    'data': [
    'security/ir.model.access.csv',
    'views/pricelist_mass_level_update_wizard_views.xml',
    ],
    'application': False,
}