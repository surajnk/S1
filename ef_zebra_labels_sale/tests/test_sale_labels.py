# -*- coding: utf-8 -*-
# Plain unittest, no Odoo needed:  cd ef_zebra_labels_sale/tests && python3 -m unittest test_sale_labels
import importlib.util
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.dirname(HERE)
LABELS = os.path.join(MODULE, "zpl", "sale.order.line")
CORE = os.path.join(os.path.dirname(MODULE), "ef_zebra_labels")
spec = importlib.util.spec_from_file_location("zpl_utils", os.path.join(CORE, "zpl_utils.py"))
zpl_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zpl_utils)

VALUES = {
    "customer": "INTERNATIONAL PACKAGING", "order_name": "M94932", "part_desc": "70 RAINBOW MIDNIGHT",
    "ref1": "CBM406979", "po": "4500144610", "uom": "Yards", "item_qty": "1", "size": "54x50",
    "putups": "50", "prod_date": "10/25/2026", "embossing": "Rainbow", "copies": 3,
}


class TestLabels(unittest.TestCase):
    def test_all_labels_listed_with_names(self):
        labels = dict(zpl_utils.list_labels(LABELS))
        self.assertEqual(sorted(labels), ["CAR635", "CRE500", "ECO515", "ECO525", "INT505"])
        self.assertEqual(labels["INT505"], "INTERNATIONAL PACKAGING (INT505)")

    def test_every_label_renders_cleanly(self):
        for code, _name in zpl_utils.list_labels(LABELS):
            out = zpl_utils.render(zpl_utils.read_label(LABELS, code), VALUES)
            self.assertNotIn("{{", out, code)
            self.assertNotIn("^XA", out, code)  # wrapper comes from zebra.printer
            self.assertNotIn("^XZ", out, code)
            self.assertTrue(out.rstrip().endswith("^PQ3"), code)

    def test_values_are_escaped(self):
        out = zpl_utils.render("^FD{{ a }}^FS", {"a": "AC^ME~ \n x"})
        self.assertEqual(out, "^FDACME x^FS")

    def test_missing_value_reported(self):
        with self.assertRaises(KeyError) as ctx:
            zpl_utils.render("{{ a }}{{ b }}", {"a": 1})
        self.assertEqual(ctx.exception.args[0], "b")

    def test_code_cannot_escape_folder(self):
        with self.assertRaises(ValueError):
            zpl_utils.read_label(LABELS, "../../__init__")

    def test_int505_matches_original_commands(self):
        out = zpl_utils.render(zpl_utils.read_label(LABELS, "INT505"), VALUES)
        self.assertIn("^FT150,1410^A0B,48,40^CI0^FDINTERNATIONAL PACKAGING - M94932^FS", out)
        self.assertIn("^FT505,1410^BCB,150,Y,N,N^FDCBM406979^FS", out)


if __name__ == "__main__":
    unittest.main()
