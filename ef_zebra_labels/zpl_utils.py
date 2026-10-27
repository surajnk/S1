# -*- coding: utf-8 -*-
"""Odoo-free helpers for ZPL label files, kept separate so they can be unit tested."""
import os
import re

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")
_FX_NAME = re.compile(r"^\^FX\s*(.+?)\s*$", re.M)


def zpl_text(value):
    """Make a value safe for ^FD: ^ and ~ start ZPL commands, so drop them."""
    if value is None or value is False:
        return ""
    text = str(value).replace("^", "").replace("~", "")
    return " ".join(text.split())


def list_labels(directory):
    """Return [(code, name)] for every <CODE>.zpl in directory.

    The name is taken from the first ``^FX`` comment line of the file.
    """
    labels = []
    if not os.path.isdir(directory):
        return labels
    for fname in sorted(os.listdir(directory)):
        code, ext = os.path.splitext(fname)
        if ext.lower() != ".zpl":
            continue
        match = _FX_NAME.search(read_label(directory, code))
        labels.append((code, match.group(1) if match else code))
    return labels


def read_label(directory, code):
    path = os.path.join(directory, code + ".zpl")
    # code comes from a user selection; never let it leave the label folder
    if os.path.basename(code) != code or not os.path.isfile(path):
        raise ValueError("Unknown label code %r" % code)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def render(body, values):
    """Replace {{ key }} placeholders with ZPL-safe values.

    Raises KeyError listing every placeholder the label needs but values lacks.
    """
    missing = sorted({k for k in _PLACEHOLDER.findall(body) if k not in values})
    if missing:
        raise KeyError(", ".join(missing))
    return _PLACEHOLDER.sub(lambda m: zpl_text(values[m.group(1)]), body)
