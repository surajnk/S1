# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request

class Http(models.AbstractModel):
    _inherit = 'ir.http'
    
    def session_info(self):
        res = super(Http, self).session_info()
        user = request.env.user
        res['has_advance_search_group'] = user.group_search_date_range
        return res