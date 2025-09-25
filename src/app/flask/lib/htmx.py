"""HTMX utilities for fragment extraction and manipulation."""

# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

from lxml import etree

from app.flask.extensions import htmx


def extract_fragment(html: str, id: str = "", selector: str = "") -> str:
    if not htmx:
        return html

    try:
        parser = etree.HTMLParser()
        tree = etree.fromstring(html, parser)
        if id:
            selector = f'//*[@id="{id}"]'
        node = tree.xpath(selector)[0]
        html = etree.tounicode(node, method="html")
        return html
    except Exception:
        # FIXME: this shouldn't happen
        return html
