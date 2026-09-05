# -*- coding: utf-8 -*-
import logging
import subprocess

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def mm_to_dots(mm, dpi_int):
    # 1 inch = 25.4 mm; dots = inches * dpi
    return int(round((mm / 25.4) * dpi_int))


class ZebraPrinter(models.Model):
    _name = "zebra.printer"
    _description = "Zebra / ZPL Printer (CUPS/LPD Queue)"
    _order = "sequence, name"

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    name = fields.Char(
        "Name",
        required=True,
        help="Friendly name, e.g. 'Receiving / lr031s'"
    )

    queue_name = fields.Char(
        "CUPS Queue Name",
        required=True,
        help="Must match `lpstat -p` name, e.g. lr031s"
    )

    # Odoo 14 wants selection keys to be strings, not ints.
    dpi = fields.Selection(
        [
            ("203", "203 dpi"),
            ("300", "300 dpi"),
            ("600", "600 dpi"),
        ],
        string="DPI",
        default="203",
        required=True,
        help="ZT230 typically 203 dpi unless upgraded."
    )

    label_width_mm = fields.Float(
        "Label Width (mm)",
        required=True,
        default=101.6,  # 4 inch
    )
    label_height_mm = fields.Float(
        "Label Height (mm)",
        required=True,
        default=203.2,  # 8 inch
    )

    darkness = fields.Integer(
        "Darkness (0-30)",
        default=15,
        help="^MD value"
    )
    speed = fields.Integer(
        "Print Speed IPS (1-14)",
        default=4,
        help="^PR value"
    )

    notes = fields.Text("Notes / Location / Usage")

    @api.constrains("queue_name")
    def _check_queue_name(self):
        for rec in self:
            if not rec.queue_name or " " in rec.queue_name.strip():
                raise ValidationError(_("Queue name invalid. Use plain CUPS name like lr031s."))

    def _cups_send_raw(self, raw_bytes):
        """Send bytes directly to the queue using lp -o raw."""
        self.ensure_one()
        if not self.queue_name:
            raise UserError(_("No queue_name configured on printer '%s'") % self.name)

        try:
            subprocess.run(
                ["lp", "-d", self.queue_name, "-o", "raw"],
                input=raw_bytes,
                check=True
            )
            _logger.info("Sent job to printer %s (queue %s)", self.name, self.queue_name)
        except Exception as e:
            _logger.exception("CUPS send failed for printer %s", self.name)
            raise UserError(_("Printing failed for %s: %s") % (self.name, e))

    def _build_zpl_header_footer(self):
        """Return (header, footer) ZPL strings per printer profile."""
        self.ensure_one()

        # self.dpi is now "203" / "300" / "600", so cast to int
        dpi_val = int(self.dpi)

        width_dots = mm_to_dots(self.label_width_mm, dpi_val)
        height_dots = mm_to_dots(self.label_height_mm, dpi_val)

        darkness = min(max(self.darkness, 0), 30)
        speed = min(max(self.speed, 1), 14)

        header = [
            "^XA",
            f"^MD{darkness}",            # Darkness
            f"^PR{speed}",               # Print speed (ips)
            f"^PW{width_dots}",          # Print width in dots
            f"^LL{height_dots}",         # Label length in dots
            "^LH0,0",                    # Label home
        ]
        footer = ["^XZ"]
        return "\n".join(header), "\n".join(footer)

    def print_label(self, zpl_body):
        """
        zpl_body: string WITHOUT ^XA/^XZ.
        We'll wrap and send through lp -o raw to self.queue_name.
        """
        self.ensure_one()

        if not zpl_body or not zpl_body.strip():
            raise UserError(_("Empty ZPL body. Nothing to print."))

        header, footer = self._build_zpl_header_footer()
        final_zpl = f"{header}\n{zpl_body}\n{footer}"

        _logger.debug("Final ZPL for %s:\n%s", self.name, final_zpl)
        self._cups_send_raw(final_zpl.encode("utf-8"))

    def action_test_print(self):
        """Button in form view to verify queue works."""
        for rec in self:
            header, footer = rec._build_zpl_header_footer()
            test_body = f"""
                ^FO40,40^A0N,48,48^FDTEST PRINT {rec.name}^FS
                ^FO40,110^A0N,32,32^FDQueue:{rec.queue_name}^FS
                ^FO40,160^BY3
                ^BCN,120,Y,N,N
                ^FD123456789012^FS
                """
            final_zpl = f"{header}\n{test_body}\n{footer}"
            rec._cups_send_raw(final_zpl.encode("utf-8"))
