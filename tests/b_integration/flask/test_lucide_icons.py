# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Lucide icons are inlined server-side, without the Lucide script."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import render_template

if TYPE_CHECKING:
    from flask import Flask


def test_the_footer_icons_are_inline_svg(app: Flask) -> None:
    with app.test_request_context():
        html = render_template("fragments/footer-logos.j2")

    assert "<!-- icon: lucide/github -->" in html
    assert "<!-- icon: lucide/linkedin -->" in html
    assert "data-lucide" not in html
