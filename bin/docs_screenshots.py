#!/usr/bin/env python
"""Capture screenshots of Aipress24 for the user guide.

Logs into a target instance with a test account (read from the profiles
CSV) and captures a curated list of pages to an output folder.

Examples:
    # Full set as the default (editor-in-chief) account:
    uv run python bin/docs_screenshots.py

    # Just Com'room, as a PR/communicant account (journalists can't):
    uv run python bin/docs_screenshots.py \
        --email erick+AmandaSuarez@agencetca.info --only comroom
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeout, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "local-notes" / "00-ListeDesProfilsDeTests-7.2.csv"
BASE = "https://aipress24.com"
VIEWPORT = {"width": 1440, "height": 960}

# Static pages: (slug, path, optional wait-selector).
PAGES: list[tuple[str, str, str | None]] = [
    ("news-feed", "/wire", None),
    ("social-wall", "/swork", None),
    ("members-directory", "/swork/members/", None),
    ("organisations", "/swork/organisations/", None),
    ("groups", "/swork/groups/", None),
    ("work-dashboard", "/wip", None),
    ("newsroom", "/wip/newsroom", None),
    ("newsroom-articles", "/wip/articles/", None),
    ("article-new", "/wip/articles/new/", 'input[name="titre"]'),
    ("newsroom-avis-enquete", "/wip/avis-enquete/", None),
    ("comroom", "/wip/comroom", None),
    ("eventroom", "/wip/eventroom", None),
    ("opportunities", "/wip/opportunities", None),
    ("ventes", "/wip/ventes", None),
    ("achats", "/wip/achats", None),
    ("billing", "/wip/billing", None),
    ("business-wall", "/BW/dashboard", None),
    ("preferences", "/preferences/", None),
    ("marketplace", "/biz/", None),
    ("marketplace-mission-new", "/biz/missions/new", 'input[name="title"]'),
    ("events", "/events/", None),
    ("events-calendar", "/events/calendar", None),
    ("search", "/search", None),
]

# Detail pages reached by opening a list and following the first item link:
# (slug, list_path, href_regex, [href_must_not_contain...]).
DETAILS: list[tuple[str, str, str, list[str]]] = [
    ("news-article", "/wire", r"/wire/[A-Za-z0-9]{4,}", ["/tab", "/me", "buy"]),
    ("article-view", "/wip/articles/", r"/wip/articles/\d+", ["/images"]),
    ("avis-ciblage", "/wip/avis-enquete/", r"/avis-enquete/\d+/ciblage", []),
    ("event-detail", "/events/", r"/events/\d+", ["calendar"]),
    ("member-profile", "/swork/members/", r"/members/[A-Za-z0-9]{2,}", []),
    (
        "organisation-page",
        "/swork/organisations/",
        r"/organisations/[A-Za-z0-9]{3,}",
        [],
    ),
]


def find_profile(email: str) -> dict[str, str]:
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) >= 6 and row[4].strip().lower() == email.lower():
                return {
                    "name": f"{row[0].strip()} {row[1].strip()}",
                    "email": row[4].strip(),
                    "password": row[5],  # raw (leading spaces can matter)
                }
    raise SystemExit(f"Profile {email!r} not found in {CSV_PATH}")


def login(page: Page, base: str, profile: dict[str, str]) -> bool:
    page.goto(f"{base}/auth/login", wait_until="domcontentloaded")
    _dismiss_cookie_banner(page)
    page.fill('input[name="email"]', profile["email"])
    page.fill('input[name="password"]', profile["password"])
    page.click('button[type="submit"], input[type="submit"]')
    page.wait_for_load_state("domcontentloaded")
    return "/auth/login" not in page.url


def _hide_debug_bar(page: Page) -> None:
    """Hide the fixed performance/monitoring overlay ('… SQL · GET …')."""
    try:
        page.evaluate(
            """() => {
                for (const el of document.querySelectorAll('*')) {
                    const cs = getComputedStyle(el);
                    if (cs.position === 'fixed'
                        && (el.textContent || '').includes('SQL')) {
                        el.style.display = 'none';
                    }
                }
            }"""
        )
    except Exception:
        pass


def _dismiss_cookie_banner(page: Page) -> None:
    for label in ("Accepter", "Tout accepter", "J'accepte", "Accept", "OK"):
        try:
            btn = page.get_by_role("button", name=label)
            if btn.count() and btn.first.is_visible():
                btn.first.click(timeout=1500)
                return
        except Exception:
            continue


def _shoot(page: Page, base: str, url: str, dest: Path, wait_sel: str | None) -> None:
    page.goto(
        url if url.startswith("http") else f"{base}{url}", wait_until="domcontentloaded"
    )
    _dismiss_cookie_banner(page)
    if wait_sel:
        page.wait_for_selector(wait_sel, timeout=8000)
    page.wait_for_timeout(1200)
    _hide_debug_bar(page)
    page.screenshot(path=str(dest))


def _first_detail_href(page: Page, pattern: str, exclude: list[str]) -> str | None:
    hrefs = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )
    rx = re.compile(pattern)
    for href in hrefs:
        if not href or not rx.search(href):
            continue
        if any(x in href for x in exclude):
            continue
        return href
    return None


def capture(base: str, email: str, out: Path, only: set[str] | None) -> None:
    profile = find_profile(email)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Target : {base}\nAccount: {profile['name']} <{profile['email']}>")
    print(f"Output : {out}\n")

    with sync_playwright() as pw:
        browser = pw.firefox.launch(headless=True)
        page = browser.new_context(viewport=VIEWPORT, locale="fr-FR").new_page()
        page.set_default_navigation_timeout(30_000)
        page.set_default_timeout(15_000)
        if not login(page, base, profile):
            browser.close()
            raise SystemExit(f"Login failed for {profile['email']} on {base}")
        print("Login OK\n")

        ok = fail = 0
        for slug, path, wait_sel in PAGES:
            if only and slug not in only:
                continue
            try:
                _shoot(page, base, path, out / f"{slug}.png", wait_sel)
                print(f"  [ok]   {slug:26} {path}")
                ok += 1
            except (PWTimeout, Exception) as exc:
                print(f"  [fail] {slug:26} {path}  ({type(exc).__name__})")
                fail += 1

        for slug, list_path, contains, exclude in DETAILS:
            if only and slug not in only:
                continue
            try:
                page.goto(f"{base}{list_path}", wait_until="domcontentloaded")
                page.wait_for_timeout(800)
                href = _first_detail_href(page, contains, exclude)
                if not href:
                    print(f"  [skip] {slug:26} (no item link on {list_path})")
                    fail += 1
                    continue
                _shoot(page, base, href, out / f"{slug}.png", None)
                print(f"  [ok]   {slug:26} {href}")
                ok += 1
            except (PWTimeout, Exception) as exc:
                print(f"  [fail] {slug:26} {list_path}  ({type(exc).__name__})")
                fail += 1

        browser.close()
        print(f"\nDone: {ok} captured, {fail} failed/skipped.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default=BASE)
    ap.add_argument("--email", default="erick@agencetca.info")
    ap.add_argument("--out", default=str(ROOT / "docs/src/screenshots/new"))
    ap.add_argument("--only", default="", help="comma-separated slugs to capture")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()} or None
    capture(args.base_url, args.email, Path(args.out), only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
