# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.lib.html import remove_markup


def test_remove_markup() -> None:
    html = """
    <html>
        <body>
            <p>Test</p>
        </body>
    </html>
    """
    assert remove_markup(html).strip() == "Test"
