# -*- coding: utf-8 -*-
##############################################################################
#
#    AtharvERP Business Solutions
#    Copyright (C) 2020-TODAY AtharvERP Business Solutions(<http://www.atharverp.com>).
#    Author: AtharvERP Business Solutions(<http://www.atharverp.com>)
#    you can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    GENERAL PUBLIC LICENSE (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
import datetime
from dateutil.relativedelta import relativedelta
import time


class set_filter(models.Model):
	_name = 'set.filter'
	_description = "Set Filter"


	name = fields.Char('Name', required="1")
	model_id = fields.Many2one('ir.model', string='Model', ondelete='set null')
	filter_field = fields.Many2one('ir.model.fields', string='Filter Field', ondelete="set null")
	state = fields.Selection([('draft','Draft'),('done','Done')], string='State', default='draft')
	view_id = fields.Many2one('ir.ui.view', string='Search View')
	filter_prefix = fields.Char(string='Filter Prefix', help='Prefix used in filter labels and technical names',required=True)
	today = fields.Boolean('Today')
	this_week = fields.Boolean('This Week')
	this_month = fields.Boolean('This Month')
	this_year = fields.Boolean('This Year')


	yesterday = fields.Boolean('Yesterday')
	last_7_days = fields.Boolean('Last 7 Days')
	last_30_days = fields.Boolean('Last 30 Days')
	last_365_days = fields.Boolean('Last 365 Days')

	last_week = fields.Boolean('Last Week')
	last_month = fields.Boolean('Last Month')
	last_year = fields.Boolean('Last Year')

	tomorrow = fields.Boolean('Tomorrow')
	next_7_days = fields.Boolean('Next 7 days (7 days from today)')
	next_week = fields.Boolean('Next Week (Monday to Sunday of next week)')
	next_4_weeks = fields.Boolean('Next 4 Weeks (28 days from today)')

	# _sql_constraints = [
	# 	('unique_model', 'unique(model_id)', "You can not create more then one record of same model !"),
	# ]

	def action_done(self):
		search_id = self.env['ir.ui.view'].search([('model', '=', self.model_id.model), ('type', '=', 'search')],
												  limit=1, order='priority, id')
		if not search_id:
			raise ValidationError("Search View not found in %s model" % self.model_id.name)

		view_name = 'view.dev.auto.date.' + str(self.model_id.model).replace('.', '_') + '_' + str(
			self.id) + '.inherit.filter'

		vals = {
			'name': view_name,
			'type': 'search',
			'model': self.model_id.model,
			'priority': search_id.priority,
			'active': True,
			'inherit_id': search_id and search_id.id or False,
			'mode': 'extension',
		}
		new_search_id = self.env['ir.ui.view'].create(vals)
		self.view_id = new_search_id.id

		arg = "<?xml version='1.0'?>\n"
		arg += "\t <xpath expr='//search' position='inside'>\n"

		filter_prefix = (self.filter_prefix or '').strip()
		is_datetime = self.filter_field.ttype == 'datetime'
		field_name = self.filter_field.name

		# Helper function to create filter templates
		def create_filter_template(filter_string, filter_name, date_expr1, date_expr2=None, field_name=None,
								   is_datetime=True):
			if not field_name:
				field_name = self.filter_field.name
			if date_expr2 is None:
				date_expr2 = date_expr1

			if is_datetime:
				return '''\t\t<filter string="%s" name="%s" domain="[('%s','&gt;=', %s),('%s','&lt;=',%s)]"/>\n''' % (
					filter_string, filter_name, field_name, date_expr1, field_name, date_expr2)
			else:
				return '''\t\t<filter string="%s" name="%s" domain="[('%s','&gt;=', %s),('%s','&lt;=',%s)]"/>\n''' % (
					filter_string, filter_name, field_name, date_expr1, field_name, date_expr2)

		# TODAY
		if self.today:
			filter_name = (filter_prefix + '_today').lower().replace(' ', '_') if filter_prefix else 'today'
			filter_string = (filter_prefix + ' Today') if filter_prefix else 'Today'
			arg += create_filter_template(
				filter_string, filter_name,
				"datetime.date.today().strftime('%Y-%m-%d 00:00:00')",
				"datetime.date.today().strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# YESTERDAY
		if self.yesterday:
			filter_name = (filter_prefix + '_yesterday').lower().replace(' ', '_') if filter_prefix else 'yesterday'
			filter_string = (filter_prefix + ' Yesterday') if filter_prefix else 'Yesterday'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today()-datetime.timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')",
				"datetime.date.today().strftime('%Y-%m-%d 00:00:00')",
				field_name, is_datetime
			)

		# LAST 7 DAYS
		if self.last_7_days:
			filter_name = (filter_prefix + '_7days').lower().replace(' ', '_') if filter_prefix else '7days'
			filter_string = (filter_prefix + ' Last 7 Days') if filter_prefix else 'Last 7 Days'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today()+datetime.timedelta(days=-7)).strftime('%Y-%m-%d 00:00:00')",
				"datetime.date.today().strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# LAST 30 DAYS
		if self.last_30_days:
			filter_name = (filter_prefix + '_30days').lower().replace(' ', '_') if filter_prefix else '30days'
			filter_string = (filter_prefix + ' Last 30 Days') if filter_prefix else 'Last 30 Days'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today()+datetime.timedelta(days=-30)).strftime('%Y-%m-%d 00:00:00')",
				"datetime.date.today().strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# LAST 365 DAYS
		if self.last_365_days:
			filter_name = (filter_prefix + '_365days').lower().replace(' ', '_') if filter_prefix else '365days'
			filter_string = (filter_prefix + ' Last 365 Days') if filter_prefix else 'Last 365 Days'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today()+datetime.timedelta(days=-365)).strftime('%Y-%m-%d 00:00:00')",
				"datetime.date.today().strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# THIS WEEK
		if self.this_week:
			filter_name = (filter_prefix + '_this_week').lower().replace(' ', '_') if filter_prefix else 'this_week'
			filter_string = (filter_prefix + ' This Week') if filter_prefix else 'This Week'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today()+relativedelta(weeks=-1, days=1, weekday=-1)).strftime('%Y-%m-%d 00:00:00')",
				"(datetime.date.today()+relativedelta(weeks=0, weekday=5)).strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# THIS MONTH
		if self.this_month:
			filter_name = (filter_prefix + '_this_month').lower().replace(' ', '_') if filter_prefix else 'this_month'
			filter_string = (filter_prefix + ' This Month') if filter_prefix else 'This Month'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today()+relativedelta(day=1)).strftime('%Y-%m-%d 00:00:00')",
				"(datetime.date.today()+relativedelta(day=1, months=1, days=-1)).strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# THIS YEAR
		if self.this_year:
			filter_name = (filter_prefix + '_this_year').lower().replace(' ', '_') if filter_prefix else 'this_year'
			filter_string = (filter_prefix + ' This Year') if filter_prefix else 'This Year'
			arg += create_filter_template(
				filter_string, filter_name,
				"time.strftime('%Y-01-01 00:00:00')",
				"time.strftime('%Y-12-31 23:59:59')",
				field_name, is_datetime
			)

		# LAST WEEK
		if self.last_week:
			filter_name = (filter_prefix + '_last_week').lower().replace(' ', '_') if filter_prefix else 'last_week'
			filter_string = (filter_prefix + ' Last Week') if filter_prefix else 'Last Week'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today()+relativedelta(weeks=-2, days=-1, weekday=-1)).strftime('%Y-%m-%d 00:00:00')",
				"(datetime.date.today()+relativedelta(weeks=-1, weekday=5)).strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# LAST MONTH
		if self.last_month:
			filter_name = (filter_prefix + '_last_month').lower().replace(' ', '_') if filter_prefix else 'last_month'
			filter_string = (filter_prefix + ' Last Month') if filter_prefix else 'Last Month'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today() - relativedelta(day=1, months=1)).strftime('%Y-%m-%d 00:00:00')",
				"(datetime.date.today() - relativedelta(day=31, months=1)).strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# LAST YEAR
		if self.last_year:
			filter_name = (filter_prefix + '_last_year').lower().replace(' ', '_') if filter_prefix else 'last_year'
			filter_string = (filter_prefix + ' Last Year') if filter_prefix else 'Last Year'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today() - relativedelta(day=1, month=1, years=1)).strftime('%Y-%m-%d 00:00:00')",
				"(datetime.date.today() - relativedelta(day=31, month=12, years=1)).strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# TOMORROW
		if self.tomorrow:
			filter_name = (filter_prefix + '_tomorrow').lower().replace(' ', '_') if filter_prefix else 'tomorrow'
			filter_string = (filter_prefix + ' Tomorrow') if filter_prefix else 'Tomorrow'
			if is_datetime:
				arg += create_filter_template(
					filter_string, filter_name,
					"(datetime.date.today()+datetime.timedelta(days=1)).strftime('%Y-%m-%d 00:00:00')",
					"(datetime.date.today()+datetime.timedelta(days=1)).strftime('%Y-%m-%d 23:59:59')",
					field_name, is_datetime
				)
			else:
				arg += '''\t\t<filter string="%s" name="%s" domain="[('%s','=',(datetime.date.today()+datetime.timedelta(days=1)).strftime('%%Y-%%m-%%d'))]"/>\n''' % (
					filter_string, filter_name, field_name)

		# NEXT 7 DAYS
		if self.next_7_days:
			filter_name = (filter_prefix + '_next_7_days').lower().replace(' ', '_') if filter_prefix else 'next_7_days'
			filter_string = (filter_prefix + ' Next 7 Days') if filter_prefix else 'Next 7 Days'
			arg += create_filter_template(
				filter_string, filter_name,
				"datetime.date.today().strftime('%Y-%m-%d 00:00:00')",
				"(datetime.date.today()+datetime.timedelta(days=7)).strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# NEXT WEEK
		if self.next_week:
			filter_name = (filter_prefix + '_next_week').lower().replace(' ', '_') if filter_prefix else 'next_week'
			filter_string = (filter_prefix + ' Next Week') if filter_prefix else 'Next Week'
			arg += create_filter_template(
				filter_string, filter_name,
				"(datetime.date.today()+relativedelta(weekday=0)).strftime('%Y-%m-%d 00:00:00')",
				"(datetime.date.today()+relativedelta(weekday=0)+datetime.timedelta(days=7)).strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		# NEXT 4 WEEKS
		if self.next_4_weeks:
			filter_name = (filter_prefix + '_next_4_weeks').lower().replace(' ',
																			'_') if filter_prefix else 'next_4_weeks'
			filter_string = (filter_prefix + ' Next 4 Weeks') if filter_prefix else 'Next 4 Weeks'
			arg += create_filter_template(
				filter_string, filter_name,
				"datetime.date.today().strftime('%Y-%m-%d 00:00:00')",
				"(datetime.date.today()+datetime.timedelta(weeks=4)).strftime('%Y-%m-%d 23:59:59')",
				field_name, is_datetime
			)

		arg += "\t </xpath>"
		self.view_id.arch_base = arg
		self.state = 'done'


	def action_draft(self):
		self.view_id.unlink()
		self.state = 'draft'