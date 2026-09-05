# -*- coding: utf-8 -*-
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'
    
    group_search_date_range = fields.Boolean("Odoo Advance Date Range Search", default=True)
    
    def __init__(self, pool, cr):
        """ Override of __init__ to add access rights on group_search_date_range. 
        Access rights are disabled by default, but allowed
        on some specific fields defined in self.SELF_{READ/WRITE}ABLE_FIELDS.
        """
        
        init_res = super(ResUsers, self).__init__(pool, cr)
        if 'group_search_date_range' not in self.SELF_WRITEABLE_FIELDS:
            # duplicate list to avoid modifying the original reference
            type(self).SELF_WRITEABLE_FIELDS = list(self.SELF_WRITEABLE_FIELDS)
            type(self).SELF_WRITEABLE_FIELDS.extend(['group_search_date_range'])
        if 'group_search_date_range' not in self.SELF_READABLE_FIELDS:
            # duplicate list to avoid modifying the original reference
            type(self).SELF_READABLE_FIELDS = list(self.SELF_READABLE_FIELDS)
            type(self).SELF_READABLE_FIELDS.extend(['group_search_date_range'])
        return init_res
    