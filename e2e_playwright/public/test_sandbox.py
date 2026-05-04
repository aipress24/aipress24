# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``app.modules.public.views.sandbox`` (was 31%).

The sandbox surface lists HTML fixtures used by designers / QA
to inspect raw template states without going through the full
flow. Two routes :

- ``GET /sandbox/`` — index page listing every file in
  ``modules/public/templates/sandbox-pages/``.
- ``GET /sandbox/<path>`` — returns the raw HTML of the
  matching file, or 404.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


def test_sandbox_index_lists_files(page: Page, base_url: str) -> None:
    """``/sandbox/`` renders an HTML page with at least one
    `<a href="/sandbox/...">` link per file in the templates dir."""
    resp = page.goto(
        f"{base_url}/sandbox/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status == 200, (
        f"/sandbox/ : status={resp.status if resp else '?'}"
    )
    body = page.content()
    assert "Sandbox Pages" in body, (
        "expected the index page heading to render"
    )
    # Index should list at least the known fixtures shipped with
    # the repo (`bw-edit`, `reglage-ventes-droits`).
    links = page.locator('a[href^="/sandbox/"]').evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    assert any("/sandbox/bw-edit" in (h or "") for h in links), (
        f"expected /sandbox/bw-edit in index, got {links!r}"
    )


def test_sandbox_renders_known_fixture(
    page: Page, base_url: str
) -> None:
    """``/sandbox/bw-edit`` returns the raw HTML of the fixture."""
    resp = page.goto(
        f"{base_url}/sandbox/bw-edit", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status == 200, (
        f"/sandbox/bw-edit : status={resp.status if resp else '?'}"
    )
    body = page.content()
    # Body should include some HTML content — the file exists.
    assert "<" in body and ">" in body


def test_sandbox_strips_trailing_slash(
    page: Page, base_url: str
) -> None:
    """``/sandbox/bw-edit/`` should resolve the same as
    ``/sandbox/bw-edit`` (the route does
    `path.removesuffix("/")` to handle copy-paste)."""
    resp = page.goto(
        f"{base_url}/sandbox/bw-edit/",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status == 200


def test_sandbox_unknown_path_returns_404(
    page: Page, base_url: str
) -> None:
    """``/sandbox/<unknown>`` raises NotFound."""
    resp = page.goto(
        f"{base_url}/sandbox/this-fixture-does-not-exist",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status == 404, (
        f"/sandbox/<unknown> : expected 404, got "
        f"{resp.status if resp else '?'}"
    )


@pytest.mark.parametrize("fixture", ("trix", "tiny"))
def test_sandbox_renders_template_fixtures(
    page: Page, base_url: str, fixture: str
) -> None:
    """The ``trix`` and ``tiny`` template fixtures are
    `.j2`-extension files — the route resolves them via the
    ``.html`` suffix lookup, so they should NOT match (the
    glob in the index only finds `.html` files). Test that
    they 404."""
    resp = page.goto(
        f"{base_url}/sandbox/{fixture}",
        wait_until="domcontentloaded",
    )
    # `.j2` files aren't matched by the `+ ".html"` lookup —
    # so trix/tiny respond 404.
    assert resp is not None and resp.status == 404
