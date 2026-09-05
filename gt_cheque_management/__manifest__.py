# -*- coding: utf-8 -*-
##############################################################################
#
#    Globalteckz Pvt Ltd
#    Copyright (C) 2013-Today(www.globalteckz.com).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name' : 'Cheque/Check Management in Odoo',
    'version' : '14.0',
    'author' : 'Globalteckz',
    'category' : 'Accounting',
    'description' : """
check management
cheque management
bank check
bank cheque
checks management
cheques management
bank checks
bank cheques
outgoing check
outgoing cheque
incoming check
incoming cheque
outgoing checks
outgoing cheques
incoming checks
incoming cheques
out check
out cheque
income check
income cheque
out checks
out cheques
income checks
income cheques
check management in odoo
cheque management in odoo
bank check in odoo
bank cheque in odoo
checks management in odoo
cheques management in odoo

""",
    'website': 'https://www.globalteckz.com',
    'depends' : ['base', 'account','attachment_indexation','account'],
    "license" : "Other proprietary",
    'images': ['static/description/banner.png'],
    "price": "49.00",
    "currency": "EUR",
    'data': [
        'security/ir.model.access.csv',
        'report/report_wizard_view.xml',
        'report/cheque_report.xml',
        'wizard/cheque_wizard.xml',
        'views/ir_sequence_data.xml',
        'views/cheque_manage.xml',
        'views/res_config.xml',
       # 'report/incoming_cheque_template.xml',
       # 'report/outgoing_cheque_template.xml',
        
    ],
    'qweb' : [
    ],
    'test': [
    ],
    'installable': True,
    'auto_install': False,
}
