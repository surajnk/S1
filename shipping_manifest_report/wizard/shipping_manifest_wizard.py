from datetime import datetime, time
from fractions import Fraction
import pytz

from odoo import fields, models

# EFMC client timezone (see memory) - scheduled_date is stored UTC on
# stock.picking, so the wizard's Date needs to be widened to a UTC
# datetime range in this timezone before filtering.
CLIENT_TZ = 'America/New_York'


class ShippingManifestWizard(models.TransientModel):
    _name = 'shipping.manifest.wizard'
    _description = 'Shipping Manifest Report Wizard'

    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
    )

    def action_print_report(self):
        """Entry point triggered by the wizard's Print/Generate button."""
        self.ensure_one()
        return self.env.ref(
            'shipping_manifest_report.action_report_shipping_manifest'
        ).report_action(self)

    def _get_day_bounds_utc(self):
        """Local calendar day (self.date, in CLIENT_TZ) -> UTC datetime bounds."""
        tz = pytz.timezone(CLIENT_TZ)
        local_start = tz.localize(datetime.combine(self.date, time.min))
        local_end = tz.localize(datetime.combine(self.date, time.max))
        return (
            local_start.astimezone(pytz.utc).replace(tzinfo=None),
            local_end.astimezone(pytz.utc).replace(tzinfo=None),
        )

    def _get_report_data(self):

        self.ensure_one()
        date_from, date_to = self._get_day_bounds_utc()

        shipped_pickings = self.env['stock.picking'].search([
            ('picking_type_id.code', '=', 'outgoing'),
            ('state', '=', 'done'),
            ('date_done', '>=', date_from),
            ('date_done', '<=', date_to),
        ])

        bol_delivery_ids = self.env['bill.of.leading.wiz'].sudo().search(
            []
        ).mapped('delivery_order_ids').ids

        pending_pickings = self.env['stock.picking'].search([
            ('id', 'in', bol_delivery_ids),
            ('state', 'not in', ['done', 'cancel']),
            ('date_deadline', '<=', date_to),
        ])

        return {
            'shipped': self._build_lines(shipped_pickings),
            'pending': self._build_lines(pending_pickings),
        }

    def _get_bol_for_picking(self, picking):
        return self.env['bill.of.leading.wiz'].sudo().search([
            ('delivery_order_ids', 'in', picking.id),
        ], order='id desc', limit=1)

    def _get_units_label(self, move):
        packaged_lines = move.move_line_ids.filtered(lambda l: l.result_package_id)
        if not packaged_lines:
            return '%s %s' % (move.product_uom_qty, move.product_uom.name)
        type_counts = {}
        for pkg in packaged_lines.mapped('result_package_id'):
            type_name = pkg.packaging_id.shipper_package_code or 'Package'
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        return ', '.join(
            '%d %s(s)' % (count, name) for name, count in type_counts.items()
        )

    def _get_weight_for_move(self, move):
        packages = move.move_line_ids.mapped('result_package_id')
        if not packages:
            return move.weight if 'weight' in move._fields else 0.0
        return sum(packages.mapped('shipping_weight'))

    def _get_sale_line_for_move(self, move, picking):
        if move.sale_line_id:
            return move.sale_line_id
        if picking.origin:
            order = self.env['sale.order'].search(
                [('name', '=', picking.origin)], limit=1
            )
            if order:
                return order.order_line.filtered(
                    lambda l: l.product_id == move.product_id
                )[:1]
        return self.env['sale.order.line']

    def _get_mo_for_move(self, move, picking):
        seen = self.env['stock.move']
        queue = move
        while queue:
            current = queue[0]
            queue = queue[1:]
            if current in seen:
                continue
            seen |= current
            if current.production_id:
                return current.production_id
            if current.raw_material_production_id:
                return current.raw_material_production_id
            queue += current.move_orig_ids
        if picking.origin:
            return self.env['mrp.production'].search(
                [('name', '=', picking.origin)], limit=1
            )
        return self.env['mrp.production']

    def _format_dimension(self, value):
        if not value:
            return ''
        whole = int(value)
        frac = Fraction(value - whole).limit_denominator(16)
        if not frac:
            return '%d"' % whole
        if whole:
            return '%d-%d/%d"' % (whole, frac.numerator, frac.denominator)
        return '%d/%d"' % (frac.numerator, frac.denominator)

    def _format_size(self, width, length):
        """width x length -> '40" X 26"'. Length omitted entirely when
        blank/zero (some order lines only carry a width)."""
        width_str = self._format_dimension(width)
        if not length:
            return width_str
        length_str = self._format_dimension(length)
        return ' X '.join(filter(None, [width_str, length_str]))

    def _get_sta_label(self, mo, sale_line, picking):
        """'I' (in progress/under-shipped) overrides 'C' (done) whenever the
        shipped qty (sale line's Delivered) hasn't caught up with what the
        linked MO produced. 'NA' when there's no linked MO."""
        if not mo:
            return 'NA'
        if sale_line.qty_delivered < sale_line.product_uom_qty:
            return 'I'
        return 'C' if picking.state == 'done' else picking.state

    def _build_lines(self, pickings, bol=None):
        lines = []
        for picking in pickings:
            picking_bol = bol or self._get_bol_for_picking(picking)
            bol_number = ''
            if picking_bol:
                bol_number = (
                    picking_bol.bill_manual_no
                    if picking_bol.is_manual_bill_no
                    else picking_bol.bill_auto_no
                )
            bol_number = bol_number or picking.name

            for move in picking.move_ids_without_package:
                if move.state == 'cancel':
                    continue
                sale_line = self._get_sale_line_for_move(move, picking)
                order = sale_line.order_id
                mo = self._get_mo_for_move(move, picking)

                line = {
                    'cust': picking.partner_id.ref or picking.partner_id.name or '',
                    'ship_to': picking.partner_id.name or '',
                    'po': order.client_order_ref or '',
                    'product': move.product_id.display_name,
                    'order': ' / '.join(filter(None, [order.name, mo.name])),
                    # TODO: confirm source for "Size" - no standard field;
                    # using variant attribute values as a placeholder.
                    'size': self._format_size(
                            sale_line.x_customer_order_width,
                            sale_line.x_customer_order_length,
                        ),
                    'carrier_terms': ' - '.join(filter(None, [
                        picking.ship_via_id.x_name if picking.ship_via_id else picking.carrier_id.name,
                        order.incoterm.code if order.incoterm else '',
                    ])),
                    'sta': self._get_sta_label(mo, sale_line, picking),
                    'units': self._get_units_label(move),
                    # TODO: confirm "Ship Amount" - placeholder mirrors qty
                    # in the move's UoM (e.g. yards).
                    'ship_amount': move.product_uom_qty,
                    'weight': self._get_weight_for_move(move),
                    'bol': bol_number,
                    # TODO: confirm source for "Exp" flag column.
                    'exp': '',
                }
                if picking_bol:
                    line['created'] = fields.Date.to_string(picking_bol.create_date)
                    line['shp_dte'] = fields.Date.to_string(picking_bol.ship_date)
                lines.append(line)
        return lines
