from odoo import models, fields, api, _


class DefectMaster(models.Model):
    _name = "defect.master"
    _description = "Defect Master"
    _rec_name = "defect"


    work_id = fields.Many2one('mrp.workcenter', string='Area')
    defect = fields.Char(string="Defect")
