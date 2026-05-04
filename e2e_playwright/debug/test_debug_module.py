# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for ``app.modules.debug`` (was 45%).

The debug module exposes 4 routes gated by ``UNSECURE=True`` :

- ``GET /debug/`` — JSON dump of `current_app.config` + env vars.
- ``GET /debug/db`` — JSON with the SQLAlchemy URI + engine repr.
- ``GET /debug/env`` — text/HTML dump of os.environ.
- ``GET /debug/config`` — text/HTML dump of app.config.

Each route is preceded by a ``before_request`` hook
(`check_debug`) that raises Unauthorized when ``UNSECURE`` is
False — that branch is covered by hitting any debug URL with
the gate disabled (we can't simulate that from outside without
poking the config, so we just skip when the gate's open).
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page


def test_debug_root_returns_json_config_and_env(
    page: Page, base_url: str
) -> None:
    """``GET /debug/`` returns a JSON document with ``config``
    and ``env`` keys."""
    resp = page.goto(
        f"{base_url}/debug/", wait_until="domcontentloaded"
    )
    if resp is None or resp.status == 401:
        pytest.skip("UNSECURE gate is closed")
    assert resp.status == 200
    body = page.content()
    # The JSON document is wrapped in HTML by the browser viewer
    # — extract from the <pre> or fetch the URL via the API to
    # get the raw bytes.
    raw = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {credentials: 'same-origin'});
            return await r.text();
        }""",
        f"{base_url}/debug/",
    )
    data = json.loads(raw)
    assert "config" in data, body
    assert "env" in data, body
    assert isinstance(data["config"], dict)
    assert isinstance(data["env"], dict)


def test_debug_db_returns_uri_and_engine(
    page: Page, base_url: str
) -> None:
    """``GET /debug/db`` returns JSON with the DB URI and engine
    repr — sanity check on the ORM init."""
    page.goto(f"{base_url}/", wait_until="commit")
    raw = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {credentials: 'same-origin'});
            return {status: r.status, text: await r.text()};
        }""",
        f"{base_url}/debug/db",
    )
    if raw["status"] == 401:
        pytest.skip("UNSECURE gate is closed")
    assert raw["status"] == 200
    data = json.loads(raw["text"])
    assert "SQLALCHEMY_DATABASE_URI" in data
    assert "DB_ENGINE" in data


def test_debug_env_renders_pre(page: Page, base_url: str) -> None:
    """``GET /debug/env`` returns a `<pre>`-wrapped dump of
    os.environ. Each line is `KEY=value`."""
    resp = page.goto(
        f"{base_url}/debug/env", wait_until="domcontentloaded"
    )
    if resp is None or resp.status == 401:
        pytest.skip("UNSECURE gate is closed")
    assert resp.status == 200
    body = page.content()
    assert "<pre>" in body
    assert "PATH=" in body or "USER=" in body or "HOME=" in body


def test_debug_config_renders_pre(page: Page, base_url: str) -> None:
    """``GET /debug/config`` returns a `<pre>`-wrapped dump of
    app.config. Pin a few well-known keys we set ourselves."""
    resp = page.goto(
        f"{base_url}/debug/config", wait_until="domcontentloaded"
    )
    if resp is None or resp.status == 401:
        pytest.skip("UNSECURE gate is closed")
    assert resp.status == 200
    body = page.content()
    assert "<pre>" in body
    # MAX_FORM_MEMORY_SIZE was set explicitly in main.py
    # (bug #0106 fix), so we know it's in the config dump.
    assert "MAX_FORM_MEMORY_SIZE" in body
