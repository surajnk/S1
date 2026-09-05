# -*- coding: utf-8 -*-
from odoo import models, fields

class MrpWoRollLine(models.Model):
    _inherit = 'mrp.wo.roll.line'

    production_id = fields.Many2one(
        'mrp.production',
        string='Manufacturing Order',
        related='workorder_id.production_id',
        store=False,
    )
    roll_material_value = fields.Float(
        string='Roll Material Value',
        digits='Product Price',
        readonly=True,
        copy=False,
    )
    roll_labour_ovh_value = fields.Float(
        string='Roll Labour & Overhead Value',
        digits='Product Price',
        readonly=True,
        copy=False,
    )
    roll_wip_value = fields.Float(
        string='Roll WIP Value',
        digits='Product Price',
        readonly=True,
        copy=False,
    )
    roll_journal_entry_id = fields.Many2one(
        'account.move',
        string='Semi-Fin Journal Entry',
        copy=False,
        readonly=True,
    )