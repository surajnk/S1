# -*- coding: utf-8 -*-
# Plain unittest, no Odoo needed:  cd ef_zebra_labels/tests && python3 -m unittest test_zpl_utils
import datetime
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("zpl_utils", os.path.join(os.path.dirname(HERE), "zpl_utils.py"))
zpl_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zpl_utils)


class TestZplUtils(unittest.TestCase):
    def test_values_are_escaped(self):
        self.assertEqual(zpl_utils.render("^FD{{ a }}^FS", {"a": "AC^ME~ \n x"}), "^FDACME x^FS")

    def test_missing_value_lists_names(self):
        with self.assertRaises(KeyError) as cm:
            zpl_utils.render("{{ a }}{{ b }}", {})
        self.assertEqual(cm.exception.args[0], "a, b")

    def test_normalize_body(self):
        self.assertEqual(zpl_utils.normalize_body("^XA\n^FDx^FS\n^XZ"), "^FDx^FS\n^PQ{{ copies }}")
        self.assertEqual(zpl_utils.normalize_body("^FDx^FS^PQ2"), "^FDx^FS^PQ2")

    def test_placeholders(self):
        self.assertEqual(zpl_utils.placeholders("{{ b }} {{a}} {{ b }}"), ["a", "b"])

    def test_expression_paths(self):
        self.assertEqual(zpl_utils.expression_paths("{a.b:%g}x{c}"), ["a.b", "c"])

    def test_expand_numbers_dates_and_text(self):
        values = {"w": 26.0, "l": 20.0, "qty": 1000.0, "d": datetime.date(2026, 11, 1), "n": "PO1", "e": False}
        get = values.get
        self.assertEqual(zpl_utils.expand("{w:%g}x{l:%g}", get), "26x20")
        self.assertEqual(zpl_utils.expand("{qty}", get), "1000")
        self.assertEqual(zpl_utils.expand("{d:%m/%d/%Y}", get), "11/01/2026")
        self.assertEqual(zpl_utils.expand("PO {n}", get), "PO PO1")
        self.assertEqual(zpl_utils.expand("[{e}]", get), "[]")

    def test_bad_number_format(self):
        with self.assertRaises(ValueError):
            zpl_utils.expand("{x:%s%s}", {"x": 1.0}.get)


if __name__ == "__main__":
    unittest.main()
