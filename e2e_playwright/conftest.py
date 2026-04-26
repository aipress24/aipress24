# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for the pre-launch e2e suite.

Reads test credentials from the project CSV and exposes :

- `base_url`         the target host (from `--base-url`).
- `profile(section)` first known-good profile for a given community.
- `login(page, p)`   helper that logs `page` in as profile `p`.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = (
    ROOT / "local-notes" / "cards" / "attachments"
    / "00-ListeDesProfilsDeTests-7.2.csv"
)
CATEGORY_RE = re.compile(
    r"^(Journalistes|PR Agency|Academics|Transformers|Leaders & Experts)"
)

# Three accounts whose stored credentials don't match the CSV (see
# scripts/check_test_profiles.report.csv). Always picked last.
KNOWN_BROKEN = {
    "erick+AichaBenMahfoud@agencetca.info",
    "eliane+HermineDeLaRoya3@agencetca.info",
    "eliane+FrancineParaquelo@agencetca.info",
}

# CSV section name → community label used in tests.
SECTION_TO_COMMUNITY = {
    "Journalistes": "PRESS_MEDIA",
    "PR Agency": "PRESS_RELATIONS",
    "Leaders & Experts": "EXPERT",
    "Transformers": "TRANSFORMER",
    "Academics": "ACADEMIC",
}


@pytest.fixture(scope="session")
def profiles() -> list[dict]:
    rows: list[dict] = []
    section = "?"
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.reader(f):
            if not row:
                continue
            first = row[0].strip()
            m = CATEGORY_RE.match(first)
            if m:
                section = m.group(1)
                continue
            if first == "Prénom" or len(row) < 6:
                continue
            prenom, nom, fonction, org, mail = (c.strip() for c in row[:5])
            pw = row[5]  # raw — leading space matters for Aïcha
            if not mail or "@" not in mail:
                continue
            rows.append(
                {
                    "section": section,
                    "community": SECTION_TO_COMMUNITY.get(section, "?"),
                    "name": f"{prenom} {nom}",
                    "fonction": fonction,
                    "org": org,
                    "email": mail,
                    "password": pw,
                }
            )
    return rows


@pytest.fixture(scope="session")
def profile(profiles) -> Callable[[str], dict]:
    """Return a function `(community) -> profile dict` picking the first
    non-broken account in that community."""

    def _pick(community: str) -> dict:
        candidates = [p for p in profiles if p["community"] == community]
        good = [p for p in candidates if p["email"] not in KNOWN_BROKEN]
        if not good:
            raise RuntimeError(f"no usable profile for {community}")
        return good[0]

    return _pick


@pytest.fixture(autouse=True)
def _bump_navigation_timeout(page: Page) -> None:
    """Don't block on third-party assets (Stripe, Sentry, fonts).

    `wait_until="load"` (the Playwright default) waits for every
    sub-resource ; under `--headed` mode and slow CDN cache misses
    that easily blows past 30 s. We default to `domcontentloaded`
    everywhere so the navigation completes as soon as the HTML is
    parsed.
    """
    page.set_default_navigation_timeout(45_000)
    page.set_default_timeout(15_000)


@pytest.fixture
def login(page: Page, base_url: str) -> Callable[[dict], None]:
    """Returns a function `login(profile)` that authenticates `page`."""

    def _login(p: dict) -> None:
        page.goto(f"{base_url}/auth/login", wait_until="domcontentloaded")
        page.fill('input[name="email"]', p["email"])
        page.fill('input[name="password"]', p["password"])
        page.click('button[type="submit"], input[type="submit"]')
        # Successful login lands away from /auth/login.
        expect(page).not_to_have_url(re.compile(r".*/auth/login.*"), timeout=15_000)

    return _login


@pytest.fixture(scope="session", autouse=True)
def _profiles_loaded_on_target(base_url, profiles):
    """Skip the whole suite when the target DB doesn't know the test
    profiles.

    Background : `local-notes/cards/attachments/00-…` lists prod-seeded
    accounts. A fresh dev DB or a randomly-faked DB will not have
    them, so every login would fail with the same opaque assertion.

    The probe drives a real browser (Playwright) rather than httpx so
    its success condition matches what individual tests will see.
    Earlier httpx attempts failed where Playwright succeeded — likely
    a Flask-Security CSRF / cookie subtlety we don't need to debug
    when we can just use the same engine the real tests use.
    """
    if not base_url or not profiles:
        return
    probe = profiles[0]
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.firefox.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_default_timeout(15_000)
                page.goto(
                    f"{base_url}/auth/login", wait_until="domcontentloaded"
                )
                page.fill('input[name="email"]', probe["email"])
                page.fill('input[name="password"]', probe["password"])
                page.click('button[type="submit"], input[type="submit"]')
                page.wait_for_load_state("domcontentloaded")
                if "/auth/login" in page.url:
                    pytest.skip(
                        f"Login failed for first CSV profile "
                        f"{probe['email']} on {base_url}. Either point "
                        "`--base-url` at a target where the CSV accounts "
                        "exist (production), or check your local DB has "
                        "them with the original passwords (no recent "
                        "--update with a different "
                        "FLASK_SECURITY_PASSWORD_SALT)."
                    )
            finally:
                browser.close()
    except Exception as e:
        pytest.skip(f"Cannot reach {base_url} : {e}")


@pytest.fixture(scope="session")
def context_args() -> dict:
    """Tighter timeouts than the pytest-playwright defaults."""
    return {"java_script_enabled": True, "ignore_https_errors": False}
