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


_XA_XZ = re.compile(r"\^X[AZ]", re.I)


def normalize_body(body):
    """Make pasted ZPL fit the printer wrapper.

    ^XA / ^XZ are added by zebra.printer, so drop them; and if the label has
    no ^PQ, append one so the Copies field is honoured.
    """
    body = _XA_XZ.sub("", body or "").strip()
    if "^PQ" not in body.upper():
        body += "\n^PQ{{ copies }}"
    return body


# ---- field expressions: "{order_id.name}", "{product_uom_qty:%g}", "{x_w:%g}x{x_l:%g}" -------------
_EXPR = re.compile(r"\{([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?::([^{}]*))?\}")


def placeholders(body):
    """Names of the {{ placeholders }} used in a ZPL body."""
    return sorted(set(_PLACEHOLDER.findall(body or "")))


def expression_paths(expression):
    """Field paths used in an expression."""
    return [m.group(1) for m in _EXPR.finditer(expression or "")]


def format_value(value, fmt=None):
    if value is None or value is False:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime(fmt or "%m/%d/%Y")
    if isinstance(value, (int, float)):
        try:
            return (fmt or "%g") % value
        except (TypeError, ValueError):
            raise ValueError("Bad number format %r" % fmt)
    return str(value)


def expand(expression, getter):
    """Replace every {path[:format]} with format_value(getter(path), format)."""
    return _EXPR.sub(lambda m: format_value(getter(m.group(1)), m.group(2)), expression or "")
