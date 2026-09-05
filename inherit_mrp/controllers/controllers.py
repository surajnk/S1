# -*- coding: utf-8 -*-
# from odoo import http


# class InheritMrp(http.Controller):
#     @http.route('/inherit_mrp/inherit_mrp/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/inherit_mrp/inherit_mrp/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('inherit_mrp.listing', {
#             'root': '/inherit_mrp/inherit_mrp',
#             'objects': http.request.env['inherit_mrp.inherit_mrp'].search([]),
#         })

#     @http.route('/inherit_mrp/inherit_mrp/objects/<model("inherit_mrp.inherit_mrp"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('inherit_mrp.object', {
#             'object': obj
#         })
