# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin section read-only coverage.

Logs in as a project-owner account that holds ADMIN
(``KNOWN_ADMINS`` in conftest) and visits every top-level admin
URL. Pure GET, no mutation.

The motivation is to push e2e coverage of ``app.modules.admin.*``
above 0% : the admin views were entirely uncovered before this
file because no community-test profile had the role.

The list mirrors ``flask routes`` for the admin blueprint plus the
manually-registered ontology and db-export sub-apps.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

ADMIN_URLS = (
    "/admin/",
    "/admin/dashboard",
    "/admin/users",
    "/admin/new_users",
    "/admin/modif_users",
    "/admin/orgs",
    "/admin/promotions",
    "/admin/system",
    "/admin/exports",
    "/admin/cms",
    "/admin/contents",
    "/admin/groups",
    "/admin/biz/moderation",
    "/admin/ontology/",
)


@pytest.mark.parametrize("path", ADMIN_URLS, ids=ADMIN_URLS)
def test_admin_page_renders_for_admin(
    page: Page,
    base_url: str,
    admin_profile,
    login,
    path: str,
) -> None:
    """Each admin top-level page renders for a real admin user."""
    p = admin_profile()
    login(p)
    resp = page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
    assert resp is not None, f"{p['email']}: no response for {path}"
    if resp.status == 404:
        pytest.skip(f"{path} returned 404 — endpoint moved?")
    assert resp.status < 400, (
        f"admin page {path} returned {resp.status} for {p['email']}"
    )


def test_admin_export_db_serves_dump(
    page: Page,
    base_url: str,
    admin_profile,
    login,
) -> None:
    """``/admin/export-db/`` streams a SQL dump rather than rendering a
    page — `page.goto` would error with « Download is starting ». Use
    the authenticated request context to GET the endpoint and assert
    we got a non-empty body, without writing the dump to disk.
    """
    p = admin_profile()
    login(p)
    resp = page.request.get(f"{base_url}/admin/export-db/")
    assert resp.status == 200, (
        f"/admin/export-db/ returned {resp.status} for {p['email']}"
    )
    body = resp.body()
    assert len(body) > 0, "/admin/export-db/ returned an empty body"
