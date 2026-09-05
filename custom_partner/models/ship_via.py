from odoo import api, fields, models
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from datetime import date
import datetime


class ShipVia(models.Model):

    _name = 'ship.via'
    _rec_name = 'x_name'

    x_name                = fields.Char(string="Name")
    x_description         = fields.Char(string="Description")
    x_reference =  fields.Char(string="Reference")