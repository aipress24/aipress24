# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``wip/views/publications.py`` (was 69%).

Two routes :

- ``GET /wip/alt-content`` — landing page (table shell, options
  list).
- ``GET /wip/alt-content/json_data`` — JSON data feeder for the
  table. Accepts ``limit``, ``offset``, ``search`` query args.

Tests :

- Index renders.
- JSON feeder returns valid JSON with ``data`` and ``total``.
- ``search`` filter narrows the result set (or stays valid for a
  needle that matches nothing).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


def test_alt_content_index_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /wip/alt-content`` renders the publications page."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(
        f"{base_url}/wip/alt-content",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/wip/alt-content : "
        f"status={resp.status if resp else '?'}"
    )
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Autres publications" in body


def test_alt_content_json_data_default(
    page: Page, base_url: str, profile, login
) -> None:
    """``GET /wip/alt-content/json_data`` (no query args) returns
    valid JSON with `data` (list) and `total` (int)."""
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(f"{base_url}/wip/", wait_until="commit")
    import json
    raw = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {credentials: 'same-origin'});
            return {status: r.status, text: await r.text()};
        }""",
        f"{base_url}/wip/alt-content/json_data",
    )
    assert raw["status"] == 200, raw
    data = json.loads(raw["text"])
    assert "data" in data and isinstance(data["data"], list), data
    assert "total" in data, data


def test_alt_content_json_data_with_search_no_match(
    page: Page, base_url: str, profile, login
) -> None:
    """``?search=`` filter that matches nothing → empty `data`,
    same `total`. Drives the `if search:` branch."""
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(f"{base_url}/wip/", wait_until="commit")
    import json
    raw = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {credentials: 'same-origin'});
            return {status: r.status, text: await r.text()};
        }""",
        f"{base_url}/wip/alt-content/json_data"
        "?search=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    )
    assert raw["status"] == 200
    data = json.loads(raw["text"])
    # No content has this string in its title → empty data.
    assert data.get("data") == [], data


@pytest.mark.parametrize("limit", (1, 5, 50))
def test_alt_content_json_data_respects_limit(
    page: Page, base_url: str, profile, login, limit: int
) -> None:
    """Pagination via ``?limit=N``. Driven through the webargs
    parser path."""
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(f"{base_url}/wip/", wait_until="commit")
    import json
    raw = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {credentials: 'same-origin'});
            return {status: r.status, text: await r.text()};
        }""",
        f"{base_url}/wip/alt-content/json_data?limit={limit}",
    )
    assert raw["status"] == 200
    data = json.loads(raw["text"])
    assert len(data.get("data") or []) <= limit, (
        f"limit={limit} but got {len(data.get('data') or [])} rows"
    )
