# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import io
from functools import singledispatch
from pathlib import Path

from flask import render_template_string
from loguru import logger


@singledispatch
def to_pdf(obj, template=None) -> bytes:
    """Transform an object to PDF."""
    raise NotImplementedError(f"Cannot transform {obj} to PDF")


def generate_pdf(data: dict, template: str | Path) -> bytes:
    # Lazy import because WeasyPrint is not always installed
    try:
        from weasyprint import HTML
    except (ImportError, OSError):
        logger.exception(
            "WeasyPrint not installed properly, PDF generation will not work"
        )
        HTML = None  # noqa: N806

    if not HTML:
        return b""

    if Path(template).is_absolute():
        template_str = Path(template).read_text()
    else:
        template_str = (Path(__file__).parent / "templates" / template).read_text()

    html_str = render_template_string(template_str, **data)

    html = HTML(string=html_str)
    html.render()
    with io.BytesIO() as f:
        html.write_pdf(f)
        return f.getvalue()
