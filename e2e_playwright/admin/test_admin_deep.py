# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin deep coverage — detail pages + exports + ontology + biz
moderation.

Le smoke top-level vit dans `test_admin_coverage.py`. Ici on creuse :
- Détails user / org / validation_profile (passe par le scraping
  d'un uid depuis le listing).
- Chaque exporter de `EXPORTERS` (inscription, modification, users,
  organisations, business_walls, mixed_org_bw) — exécution réelle
  (génère un fichier ODS, on vérifie juste status + non-empty body).
- Routes ontology (list, create, edit, delete forms).
- Biz moderation listing.
- Promotions form.
- Contents listing avec POST filter.

Tous read-only ou idempotent.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

# All EXPORTERS keys from `app/modules/admin/views/_export.py`.
_EXPORTER_NAMES = (
    "inscription",
    "modification",
    "users",
    "organisations",
    "business_walls",
    "mixed_org_bw",
)


def _first_user_uid(page: Page, base_url: str) -> str | None:
    """Open /admin/users and return the first uid linked from the
    listing (looks for `/admin/show_user/<uid>` hrefs)."""
    page.goto(f"{base_url}/admin/users", wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        m = re.search(r"/admin/show_user/([^/?#]+)", href)
        if m:
            return m.group(1)
    return None


def _first_org_uid(page: Page, base_url: str) -> str | None:
    page.goto(f"{base_url}/admin/orgs", wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        m = re.search(r"/admin/show_org/([^/?#]+)", href)
        if m:
            return m.group(1)
    return None


# ─── Detail pages ──────────────────────────────────────────────────


def test_admin_show_user_detail_renders(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/show_user/<uid>`` renders for an existing user.
    Drives `ShowUserView.get` + `admin_info_context` + BW/role
    lookups."""
    p = admin_profile()
    login(p)
    uid = _first_user_uid(page, base_url)
    if uid is None:
        pytest.skip("no user uid scrapable from /admin/users")
    resp = page.goto(
        f"{base_url}/admin/show_user/{uid}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/admin/show_user/{uid} : status={resp.status if resp else '?'}"
    )
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


def test_admin_show_org_detail_renders(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/show_org/<uid>`` renders for an existing org."""
    p = admin_profile()
    login(p)
    uid = _first_org_uid(page, base_url)
    if uid is None:
        pytest.skip("no org uid scrapable from /admin/orgs")
    resp = page.goto(
        f"{base_url}/admin/show_org/{uid}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


def test_admin_validation_profile_renders(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/validation_profile/<uid>`` renders the validation
    page for an existing user."""
    p = admin_profile()
    login(p)
    uid = _first_user_uid(page, base_url)
    if uid is None:
        pytest.skip("no user uid scrapable")
    resp = page.goto(
        f"{base_url}/admin/validation_profile/{uid}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


# ─── Exports ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name", _EXPORTER_NAMES, ids=list(_EXPORTER_NAMES)
)
def test_admin_export_route_returns_file(
    page: Page,
    base_url: str,
    admin_profile,
    login,
    authed_get,
    name: str,
) -> None:
    """``/admin/export/<exporter_name>`` for each registered exporter
    returns a non-empty body (ODS / CSV file). Drives each
    `Exporter.run()` end-to-end on the seed data."""
    p = admin_profile()
    login(p)
    # Need a navigated page for authed_get.
    page.goto(f"{base_url}/admin/", wait_until="domcontentloaded")
    resp = authed_get(f"{base_url}/admin/export/{name}")
    assert resp["status"] == 200, (
        f"/admin/export/{name} : {resp}"
    )
    assert "/auth/login" not in resp["url"]
    assert resp["len"] > 0, (
        f"/admin/export/{name} : empty body"
    )


def test_admin_export_unknown_returns_404_or_redirect(
    page: Page, base_url: str, admin_profile, login, authed_get
) -> None:
    """Unknown exporter name : graceful 404 (or redirect with flash),
    not 500. Drives the `if exporter_class is None` branch."""
    p = admin_profile()
    login(p)
    page.goto(f"{base_url}/admin/", wait_until="domcontentloaded")
    resp = authed_get(f"{base_url}/admin/export/no_such_exporter")
    assert resp["status"] < 500, (
        f"/admin/export/no_such_exporter : got {resp['status']} "
        "— expected < 500"
    )


# ─── Ontology ──────────────────────────────────────────────────────


def test_admin_ontology_list_renders(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/ontology/`` lists taxonomy entries."""
    p = admin_profile()
    login(p)
    resp = page.goto(
        f"{base_url}/admin/ontology/",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


def test_admin_ontology_create_form_renders(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/ontology/create?taxonomy_name=<...>`` GET renders
    the create-entry form. Sans `taxonomy_name`, le route flashe
    une erreur et redirige vers le listing."""
    p = admin_profile()
    login(p)
    resp = page.goto(
        f"{base_url}/admin/ontology/create?taxonomy_name=sectors",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400
    assert "/admin/ontology/create" in page.url, (
        f"create form expected, got {page.url}"
    )
    assert page.locator("form").count() >= 1


def test_admin_ontology_create_without_taxonomy_redirects(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/ontology/create`` sans `taxonomy_name` query :
    flash + redirect vers le listing."""
    p = admin_profile()
    login(p)
    resp = page.goto(
        f"{base_url}/admin/ontology/create",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400
    assert "/admin/ontology" in page.url
    assert "/admin/ontology/create" not in page.url


def test_admin_ontology_create_taxonomy_form_renders(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/ontology/create-taxonomy`` GET renders."""
    p = admin_profile()
    login(p)
    resp = page.goto(
        f"{base_url}/admin/ontology/create-taxonomy",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


# ─── CMS ───────────────────────────────────────────────────────────


def test_admin_cms_list_renders(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/cms`` lists corporate pages."""
    p = admin_profile()
    login(p)
    resp = page.goto(
        f"{base_url}/admin/cms", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400


def test_admin_cms_edit_form_renders_for_known_page(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/cms/<slug>/edit`` for one of the known static-pages
    slugs (a-propos) renders the edit form."""
    p = admin_profile()
    login(p)
    resp = page.goto(
        f"{base_url}/admin/cms/a-propos/edit",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/admin/cms/a-propos/edit : status={resp.status if resp else '?'}"
    )


def test_admin_cms_preview_post_smoke(
    page: Page, base_url: str, admin_profile, login, authed_post
) -> None:
    """``POST /admin/cms/preview`` with minimal payload : drives
    the markdown preview path. Requires valid form data ;
    skip on 4xx."""
    p = admin_profile()
    login(p)
    page.goto(f"{base_url}/admin/cms", wait_until="domcontentloaded")
    resp = authed_post(
        f"{base_url}/admin/cms/preview",
        {"body_md": "# Test\n\nPreview content."},
    )
    # 200 (preview rendered) or 4xx (CSRF / form gating). Just no
    # 5xx.
    assert resp["status"] < 500, f"cms preview : {resp}"


# ─── Biz moderation ────────────────────────────────────────────────


def test_admin_biz_moderation_listing_renders(
    page: Page, base_url: str, admin_profile, login
) -> None:
    """``/admin/biz/moderation`` lists offers awaiting moderation."""
    p = admin_profile()
    login(p)
    resp = page.goto(
        f"{base_url}/admin/biz/moderation",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400


def test_admin_biz_moderation_unknown_id_no_5xx(
    page: Page, base_url: str, admin_profile, login, authed_post
) -> None:
    """``POST /admin/biz/moderation/<unknown>/{approve,reject}`` :
    no 500 expected (404 ou redirect)."""
    p = admin_profile()
    login(p)
    page.goto(
        f"{base_url}/admin/biz/moderation",
        wait_until="domcontentloaded",
    )
    for action in ("approve", "reject"):
        resp = authed_post(
            f"{base_url}/admin/biz/moderation/9999999999/{action}",
            {},
        )
        assert resp["status"] < 500, (
            f"/admin/biz/moderation/9999999999/{action} : "
            f"got {resp['status']}"
        )


# ─── Promotions / Contents / Groups POST forms ─────────────────────


def test_admin_promotions_post_no_5xx(
    page: Page, base_url: str, admin_profile, login, authed_post
) -> None:
    """``POST /admin/promotions`` avec un payload minimal — drives
    the form submission path without committing real data."""
    p = admin_profile()
    login(p)
    page.goto(
        f"{base_url}/admin/promotions",
        wait_until="domcontentloaded",
    )
    resp = authed_post(f"{base_url}/admin/promotions", {})
    assert resp["status"] < 500


def test_admin_contents_post_no_5xx(
    page: Page, base_url: str, admin_profile, login, authed_post
) -> None:
    """``POST /admin/contents`` form smoke."""
    p = admin_profile()
    login(p)
    page.goto(
        f"{base_url}/admin/contents",
        wait_until="domcontentloaded",
    )
    resp = authed_post(f"{base_url}/admin/contents", {})
    assert resp["status"] < 500


def test_admin_groups_post_no_5xx(
    page: Page, base_url: str, admin_profile, login, authed_post
) -> None:
    """``POST /admin/groups`` form smoke."""
    p = admin_profile()
    login(p)
    page.goto(
        f"{base_url}/admin/groups", wait_until="domcontentloaded"
    )
    resp = authed_post(f"{base_url}/admin/groups", {})
    assert resp["status"] < 500
