# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``wip/views/billing.py`` (was 64%).

Three routes :

- ``GET /wip/billing`` — invoice list page. Always renders, even
  with zero invoices (empty table).
- ``GET /wip/billing/get_pdf?invoice_id=<id>`` — download PDF.
  Branches : NotFound (unknown id), Unauthorized (other user's
  invoice), and the happy path that builds a PDF.
- ``GET /wip/billing/get_csv?invoice_id=<id>`` — same shape as
  PDF but builds CSV.

The happy paths require an Invoice row owned by the user. Most
seed users have zero invoices, so we only cover the error
branches reliably ; the index page renders empty regardless.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


def test_billing_index_renders_for_authed_user(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /wip/billing`` renders for any authenticated user
    (with or without invoices)."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/wip/billing", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400, (
        f"/wip/billing : status="
        f"{resp.status if resp else '?'}"
    )
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


def test_billing_get_pdf_unknown_id_returns_404(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /wip/billing/get_pdf?invoice_id=9999999999`` →
    NotFound (404) since no Invoice with that id exists."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/wip/billing/get_pdf?invoice_id=9999999999",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status == 404


def test_billing_get_csv_unknown_id_returns_404(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /wip/billing/get_csv?invoice_id=9999999999`` →
    NotFound (404)."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/wip/billing/get_csv?invoice_id=9999999999",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status == 404


def test_billing_get_pdf_missing_invoice_id_query(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /wip/billing/get_pdf`` without the ``invoice_id``
    query arg : the route's `request.args["invoice_id"]` raises
    BadRequest → 400 (or 500 depending on global error handler)."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/wip/billing/get_pdf",
        wait_until="domcontentloaded",
    )
    if resp is None:
        pytest.skip("no response")
    # Werkzeug raises BadRequest for missing required args → 400.
    # Some globally-installed error handlers may recast as 500 ;
    # accept either as long as it's not 200 (which would be a bug).
    assert resp.status in (400, 500), (
        f"expected 400/500, got {resp.status}"
    )
