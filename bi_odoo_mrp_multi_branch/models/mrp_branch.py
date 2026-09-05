# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import pycompat
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    branch_id = fields.Many2one('res.branch', string='Branch')  
    
    @api.model 
    def default_get(self, flds): 
        result = super(MrpBom, self).default_get(flds)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result  

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    branch_id = fields.Many2one('res.branch', string='Branch')
    
    @api.model 
    def default_get(self, flds): 
        result = super(MrpBomLine, self).default_get(flds)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    branch_id = fields.Many2one('res.branch', string='Branch')



    @api.onchange('product_id', 'picking_type_id', 'company_id')
    def onchange_product_id(self):
        """ Finds UoM of changed product. """
        if not self.product_id:
            self.bom_id = False
        else:
            bom = self.env['mrp.bom']._bom_find(product=self.product_id, picking_type=self.picking_type_id, company_id=self.company_id.id)
            if bom.type == 'normal':
                self.bom_id = bom.id
                self.branch_id = bom.branch_id.id
            else:
                self.bom_id = False
            self.product_uom_id = self.product_id.uom_id.id
            return {'domain': {'product_uom_id': [('category_id', '=', self.product_id.uom_id.category_id.id)]}}        

class StockMove(models.Model):
    _inherit = 'stock.move'

    branch_id = fields.Many2one('res.branch', string='Branch')


    @api.model
    def create(self, vals):

        res = super(StockMove, self).create(vals)
        for line in res:
            user_obj = self.env['res.users']
            branch_id = user_obj.browse(line.env.user.id).branch_id.id
            if line.raw_material_production_id.bom_id.branch_id :
                branch_id = line.raw_material_production_id.bom_id.branch_id.id
            line.branch_id = branch_id


        return res


    
    @api.model 
    def default_get(self, flds): 
        result = super(StockMove, self).default_get(flds)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id

        if self.raw_material_production_id.bom_id.branch_id :
            branch_id = self.raw_material_production_id.bom_id.branch_id.id
        result['branch_id'] = branch_id
        return result

class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    branch_id = fields.Many2one('res.branch', string='Branch',related="production_id.branch_id")
    # name = fields.Char(
    #     'Operation Name', 
    #     states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})
    # operation_id = fields.Many2one(
    #     'mrp.routing.workcenter', 'Operation', check_company=True,domain="[('workcenter_id', '=', workcenter_id)]")

    @api.model 
    def default_get(self, flds): 
        result = super(MrpWorkorder, self).default_get(flds)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result

    operation_work_id = fields.Many2one(
        'mrp.routing.workcenter',
        string='Operations', domain="[('workcenter_id', '=', workcenter_id)]")

    # @api.onchange('operation_work_id')
    # def onchange_workcenter_id(self):

class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    branch_id = fields.Many2one('res.branch', string='Branch')

class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    branch_id = fields.Many2one('res.branch', string='Branch') 
    
    @api.model 
    def default_get(self, flds): 
        result = super(StockMoveLine, self).default_get(flds)
        user_obj = self.env['res.users']
        branch_id = user_obj.browse(self.env.user.id).branch_id.id
        result['branch_id'] = branch_id
        return result
