from odoo import api, fields, models
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from datetime import date
import datetime


class Publisher(models.Model):

    _name = 'publisher'
    _rec_name = 'x_name'

    x_name                = fields.Char(string="Name")
  