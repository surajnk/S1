

from odoo import api, fields, models


class mreqquestconfirm(models.TransientModel):
    _name = "mrequest.comfirm"

    name = fields.Char()
    picking_id = fields.Many2one('stock.picking', string="Transfer")
    mrequest_id = fields.Many2one('project.mrequest', string="Project Request")

    def confirm_mrquest(self):
        self.mrequest_id.state = 'done'
        self.picking_id.done_mrequest = True


