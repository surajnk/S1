{
    'name': 'MRP Workorder Schedule Report',
    'version': '14.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Print a daily schedule of workorders grouped by planned date.',
    'depends': ['mrp', 'mrp_confirmed_date_base', 'mrp_mto_analytic'],
    'data': [
        'security/ir.model.access.csv',
        'data/mrp_production_trial_sequence.xml',
        'wizard/mrp_workorder_schedule_wizard_views.xml',
        'report/mrp_workorder_schedule_report_templates.xml',
        'report/mrp_workorder_schedule_report_actions.xml',
        'views/mrp_workorder_schedule_menu.xml',
        'views/mrp_production_views.xml',
    ],
    'installable': True,
    'application': False,
}
