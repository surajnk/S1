# -*- coding: utf-8 -*-
{
    'name': 'Disable Onboarding Tours',
    'summary': """
        Unregisters core onboarding tours (CRM, POS, Project, ...) so they never auto-trigger.
    """,
    'description': """
        Loads a single generic JS asset that scans the web_tour registry
        on page load and deletes any tour whose name is listed in
        DISABLED_TOUR_NAMES (see static/src/js/disable_onboarding_tours.js).

        This avoids needing a new xpath/script tag/module change for every
        extra onboarding tour you want to silence - just add the tour name
        to the list in that one file.

        Tours disabled by default:
        - crm_tour            (CRM: "Ready to boost your sales?")
        - point_of_sale_tour  (POS: "Ready to launch your point of sale?")
        - project_tour        (Project: "Want a better way to manage your projects?")

        Does not modify any core files, so it survives upgrades.
    """,
    'category': 'Extra Tools',
    'author': 'ATC ONLINE LLP',
    'company': 'ATC ONLINE LLP',
    'maintainer': 'Suraj',
    'version': '14.0.1.0',
    'depends': ['web_tour', 'crm', 'point_of_sale', 'project','mass_mailing',],
    'data': [
        'views/assets.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
