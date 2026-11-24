# -*- coding: utf-8 -*-
# Plain unittest, no Odoo needed:  cd ef_zebra_labels_sale/tests && python3 -m unittest test_seed_data
import os
import re
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data", "label_templates.xml")


class TestSeedTemplates(unittest.TestCase):
    def setUp(self):
        self.records = ET.parse(DATA).getroot().findall("record")

    def _field(self, rec, name):
        return rec.find("field[@name='%s']" % name)

    def test_all_six_templates(self):
        codes = sorted(self._field(r, "code").text for r in self.records)
        self.assertEqual(codes, ["CAR635", "CRE500", "ECO515", "ECO525", "INT505", "SHE570"])

    def test_every_placeholder_has_a_variable(self):
        for rec in self.records:
            body = self._field(rec, "zpl_body").text
            used = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", body)) - {"copies"}
            defined = set(re.findall(r"'name': '(\w+)'", self._field(rec, "variable_ids").get("eval")))
            self.assertEqual(used, defined, self._field(rec, "code").text)

    def test_no_wrapper_commands(self):
        for rec in self.records:
            body = self._field(rec, "zpl_body").text
            self.assertNotIn("^XA", body)
            self.assertNotIn("^XZ", body)
            self.assertTrue(body.rstrip().endswith("^PQ{{ copies }}"))


if __name__ == "__main__":
    unittest.main()
