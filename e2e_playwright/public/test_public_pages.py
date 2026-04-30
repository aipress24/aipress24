# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Public surfaces — anonymous-friendly pages.

Le module ``public`` est l'on-ramp avant authentification : home
landing, pages corporate (CGU, CGV, mentions légales, à-propos,
offre-*), pricing, system health endpoints. Une régression sur
ces surfaces casse le link-share marketing et la home anonyme.

Routes couvertes :

- ``GET /`` (anonymous) → redirect to ``/auth/login``.
- ``GET /`` (authenticated) → redirect to ``/wire/wire``.
- ``GET /pricing/`` — pricing landing.
- ``GET /page/<slug>`` — corporate pages : ``a-propos``, ``cgu``,
  ``confidentialite``, ``contact``, ``offre-{communicants,
  entreprises,experts,journalistes}``, ``CGV-BusinessWall``.
- ``GET /page/<unknown>`` → 404 fallback.
- ``GET /system/health`` — health probe (smoked anon).
- ``GET /system/version/`` — version info.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Static pages on disk (cf. `static-pages/`). Each must render
# anonymously without 5xx — they're the marketing/legal surface.
_STATIC_PAGES = (
    "a-propos",
    "cgu",
    "confidentialite",
    "contact",
    "offre-communicants",
    "offre-entreprises",
    "offre-experts",
    "offre-journalistes",
    "CGV-BusinessWall",
)


def _ensure_anon(page: Page, base_url: str) -> None:
    """Drop cookies so we navigate as anonymous."""
    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    page.context.clear_cookies()


def test_home_anonymous_redirects_to_login(
    page: Page, base_url: str
) -> None:
    """``/`` GET (anonymous) → 302 → /auth/login."""
    _ensure_anon(page, base_url)
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    assert "/auth/login" in page.url, (
        f"/ anonymous : expected /auth/login, got {page.url}"
    )


def test_home_authenticated_redirects_to_wire(
    page: Page, base_url: str, profile, login
) -> None:
    """``/`` GET (logged-in) → 302 → /wire/wire (which itself
    redirects to /wire/tab/<active>)."""
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(f"{base_url}/", wait_until="domcontentloaded")
    assert "/wire/" in page.url, (
        f"/ logged-in : expected /wire/* redirect, got {page.url}"
    )
    assert "/auth/login" not in page.url


def test_pricing_renders_anonymously(
    page: Page, base_url: str
) -> None:
    """``/pricing/`` is anonymous-friendly (marketing landing)."""
    _ensure_anon(page, base_url)
    resp = page.goto(
        f"{base_url}/pricing/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400, (
        f"/pricing/ : status={resp.status if resp else '?'}"
    )
    # Don't bounce to login.
    assert "/auth/login" not in page.url


@pytest.mark.parametrize("slug", _STATIC_PAGES, ids=list(_STATIC_PAGES))
def test_corporate_page_renders(
    page: Page, base_url: str, slug: str
) -> None:
    """``/page/<slug>`` for each static page on disk renders
    anonymously. Drives both the DB-CMS branch (top-level slug)
    and the filesystem fallback.
    """
    _ensure_anon(page, base_url)
    resp = page.goto(
        f"{base_url}/page/{slug}", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400, (
        f"/page/{slug} : status={resp.status if resp else '?'}"
    )
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body


def test_corporate_page_unknown_returns_404(
    page: Page, base_url: str
) -> None:
    """``/page/<unknown-slug>`` falls through DB + filesystem
    lookups → 404 with the errors/404.j2 template."""
    _ensure_anon(page, base_url)
    resp = page.goto(
        f"{base_url}/page/no-such-page-exists-anywhere",
        wait_until="domcontentloaded",
    )
    assert resp is not None
    assert resp.status == 404


def test_system_health_renders(page: Page, base_url: str) -> None:
    """``/system/health`` — probe endpoint, must respond < 400
    even for anonymous (used by Heroku healthchecks)."""
    _ensure_anon(page, base_url)
    resp = page.goto(
        f"{base_url}/system/health", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400


def test_system_version_renders(page: Page, base_url: str) -> None:
    """``/system/version/`` — version info, anon-readable."""
    _ensure_anon(page, base_url)
    resp = page.goto(
        f"{base_url}/system/version/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400
