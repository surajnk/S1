{
    'name': 'MO Workorder Rolls',
    'summary': 'Display workorders and output rolls for a manufacturing order',
    'version': '14.0.1.0.0',
    'category': 'Manufacturing',
    'author': 'Example',
    'depends': ['mrp','mrp_shop_floor_control'],
    'data': [
        'security/ir.model.access.csv',
        'views/wo_roll_summary_wizard.xml',
        'views/wo_roll_summary_action.xml',
        'views/wo_roll_summary_menu.xml',
        'report/wo_roll_summary_report.xml',
    ],
    'installable': True,
    'application': False,
}
