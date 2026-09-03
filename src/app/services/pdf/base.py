# Copyright (c) 2021-2024, Abilian SAS & TCA
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
    msg = f"Cannot transform {obj} to PDF"
    raise NotImplementedError(msg)


class PdfGenerationError(RuntimeError):
    """WeasyPrint is missing, or not installed properly."""


def generate_pdf(data: dict, template: str | Path) -> bytes:
    """Render `template` as a PDF.

    Raises `PdfGenerationError` when WeasyPrint is missing. This PDF is
    an invoice: an empty one attaches, archives and downloads like a
    real one, and nobody notices until a customer asks for theirs.
    """
    # Lazy import because WeasyPrint is not always installed
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        msg = "WeasyPrint is not installed properly; cannot generate a PDF"
        logger.exception(msg)
        raise PdfGenerationError(msg) from exc

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
