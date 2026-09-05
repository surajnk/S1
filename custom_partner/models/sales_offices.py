# -*- coding: utf-8 -*-

from odoo import api, fields, models
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from datetime import date
import datetime


class SalesOffices(models.Model):
    _name = 'sales.offices'
    _rec_name = 'x_sales_office'

  

    x_sales_office         = fields.Char(string="Sales Office")
  
