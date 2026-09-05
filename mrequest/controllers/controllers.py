# -*- coding: utf-8 -*-
# from odoo import http


# class Rebrand(http.Controller):
#     @http.route('/rebrand/rebrand/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/rebrand/rebrand/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('rebrand.listing', {
#             'root': '/rebrand/rebrand',
#             'objects': http.request.env['rebrand.rebrand'].search([]),
#         })

#     @http.route('/rebrand/rebrand/objects/<model("rebrand.rebrand"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('rebrand.object', {
#             'object': obj
#         })
