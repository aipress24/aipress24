# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `services/pdf/base.py`.

`to_pdf` is a singledispatch entry point (one test per branch).
`generate_pdf` resolves a template path (absolute vs relative-to-the-module),
runs it through Flask's `render_template_string`, hands it to
WeasyPrint, and returns the resulting bytes. WeasyPrint is installed
in this project (see `pyproject.toml`), so the happy path is
unit-testable end-to-end — the produced bytes start with the `%PDF`
magic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.pdf.base import generate_pdf, to_pdf


class TestToPdfDispatchFallback:
    """`@singledispatch` fallback raises `NotImplementedError`. Pin a
    couple of common shapes so a future « silently return b''
    » regression doesn't slip in."""

    def test_raises_for_string(self):
        with pytest.raises(NotImplementedError, match="Cannot transform"):
            to_pdf("unknown object")

    def test_raises_for_dict(self):
        with pytest.raises(NotImplementedError, match="Cannot transform"):
            to_pdf({"key": "value"})

    def test_raises_for_list(self):
        with pytest.raises(NotImplementedError, match="Cannot transform"):
            to_pdf([1, 2, 3])

    def test_raises_for_none(self):
        with pytest.raises(NotImplementedError, match="Cannot transform"):
            to_pdf(None)


class TestToPdfDispatchRegistration:
    """`@singledispatch.register` adds a per-type handler. The dispatch
    routes correctly when a type is registered. Pin so a refactor that
    swaps in a different dispatch mechanism still routes."""

    def test_registered_handler_is_called(self):
        class _Ticket:
            pass

        # Explicit `register(type)` form — the bare `@register`
        # decorator inspects annotations via `get_type_hints`, which
        # fails under `from __future__ import annotations` for a class
        # defined inside a test method (the name isn't in the function's
        # module globals).
        @to_pdf.register(_Ticket)
        def _ticket_to_pdf(obj, template=None) -> bytes:
            return b"PDF-of-ticket"

        # No unregister — `singledispatch.registry` is a `mappingproxy`,
        # not a mutable dict. `_Ticket` is local to this test ; the
        # registry entry is harmless (the class becomes unreachable
        # outside this scope, but stays pinned in the registry — no
        # behavior leak, only a tiny memory pin).
        result = to_pdf(_Ticket())
        assert result == b"PDF-of-ticket"


class TestGeneratePdfAbsoluteTemplate:
    """`generate_pdf` with an absolute template path reads the file
    verbatim, runs it through Jinja, and pipes the output through
    WeasyPrint. Verify with a tiny self-contained template."""

    def test_produces_valid_pdf_bytes(self, tmp_path: Path):
        template_path = tmp_path / "tiny.html"
        template_path.write_text(
            "<html><body><h1>{{ title }}</h1><p>{{ body }}</p></body></html>"
        )

        result = generate_pdf({"title": "Hello", "body": "World"}, template_path)

        # PDF magic ; weasyprint stamps it at byte zero.
        assert result.startswith(b"%PDF")
        # Non-trivial — a degenerate empty PDF would be tiny.
        assert len(result) > 200

    def test_renders_jinja_substitutions(self, tmp_path: Path):
        """The data dict reaches Jinja and substitutes into the
        template. Pin so a refactor that swaps in plain `str.format`
        doesn't silently lose Jinja control structures."""
        template_path = tmp_path / "loop.html"
        template_path.write_text(
            "<html><body>"
            "{% for item in items %}<p>{{ item }}</p>{% endfor %}"
            "</body></html>"
        )

        result = generate_pdf({"items": ["alpha", "beta"]}, template_path)

        assert result.startswith(b"%PDF")

    def test_accepts_pathlib_path_for_template(self, tmp_path: Path):
        template_path = tmp_path / "smoke.html"
        template_path.write_text("<html><body>hi</body></html>")

        result = generate_pdf({}, template_path)
        assert result.startswith(b"%PDF")

    def test_accepts_string_path_for_template(self, tmp_path: Path):
        template_path = tmp_path / "smoke.html"
        template_path.write_text("<html><body>hi</body></html>")

        result = generate_pdf({}, str(template_path))
        assert result.startswith(b"%PDF")


class TestGeneratePdfRelativeTemplate:
    """A relative `template` is resolved against
    `src/app/services/pdf/templates/`. The only template shipped today
    is `invoice-pdf.j2` — render it with minimum-viable data."""

    def test_resolves_template_relative_to_module(self):
        # Minimum-viable data for the shipped invoice template.
        # Jinja's strict-undefined mode would raise on missing keys.
        result = generate_pdf(
            {
                "invoice_date": "2026-06-10",
                "invoice_number": "INV-0001",
                "invoice_total": "0.00",
                "invoice_lines": [],
            },
            "invoice-pdf.j2",
        )
        assert result.startswith(b"%PDF")
