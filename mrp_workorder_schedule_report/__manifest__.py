{
    'name': 'MRP Workorder Schedule Report',
    'version': '14.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Print a daily schedule of workorders grouped by planned date.',
    'depends': ['mrp'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/mrp_workorder_schedule_wizard_views.xml',
        'report/mrp_workorder_schedule_report_templates.xml',
        'report/mrp_workorder_schedule_report_actions.xml',
        'views/mrp_workorder_schedule_menu.xml',
    ],
    'installable': True,
    'application': False,
}
