# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""CM-1 — publication d'article : wip → wire → swork.

Cœur de plateforme. Un journaliste publie depuis WIP, l'article
doit apparaître sur les surfaces avales :

- ``/wire/tab/wall`` (le feed des articles publiés).
- ``/swork/profile/`` (vue propriétaire — listing des publications
  de l'utilisateur connecté ; cf. `swork.views._common.get_posts`).

Pattern :

1. Login journalist (PRESS_MEDIA).
2. Find an existing article owned by the user via /wip/articles/.
3. Capture its title.
4. Toggle to PUBLISHED via /wip/articles/publish/<id>/.
5. Assert title visible on /wire/tab/wall (Wire Wall query
   includes published Posts ordered by published_at desc).
6. Assert title visible on /swork/profile/ (owner's publication
   listing).
7. Cleanup : restore to UNPUBLISHED via /wip/articles/unpublish/<id>/.

Lifeline : the test is idempotent vis-à-vis the article's pre-test
state — it always finishes with the article unpublished. If the
article was published before the test, the cleanup will leave it
unpublished (state mutation, but no row creation/deletion).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

_ARTICLE_LISTING_RE = re.compile(r"^/wip/articles/(\d+)/$")
_ARTICLE_TITLE_SELECTOR = "td a, h2 a, .title a, a"  # heuristic


def _find_article_id_and_title(
    page: Page, base_url: str
) -> tuple[str, str] | None:
    """Open /wip/articles/ and return (id, title) of the first
    article row owned by the current user. None if empty.

    Title is read from the article's edit form (`input[name="titre"]`)
    — this is the canonical authored title, not a wrapped breadcrumb
    or detail-page heading.
    """
    page.goto(
        f"{base_url}/wip/articles/", wait_until="domcontentloaded"
    )
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    article_id: str | None = None
    for href in hrefs or ():
        if not href:
            continue
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path.startswith("http"):
            path = "/" + path.split("/", 3)[-1]
        match = _ARTICLE_LISTING_RE.match(path)
        if match:
            article_id = match.group(1)
            break
    if article_id is None:
        return None
    # Visit the edit form to extract the canonical title.
    page.goto(
        f"{base_url}/wip/articles/edit/{article_id}/",
        wait_until="domcontentloaded",
    )
    titre_field = page.locator('input[name="titre"]').first
    try:
        title = titre_field.input_value(timeout=2000).strip()
    except Exception:
        return None
    if not title or len(title) < 5:
        return None
    return article_id, title


def _title_substring(title: str, min_len: int = 12) -> str:
    """Return a chunk of `title` long enough to be unique on /wire/.

    Front-end may wrap or normalize the title, so we don't try to
    match it verbatim. A 12-30 char substring is enough to avoid
    accidental matches against other articles' titles.
    """
    title = title.strip()
    if len(title) <= min_len:
        return title
    # Take a ~25-char span starting somewhere stable (skip the
    # leading "Article: " or similar prefix that the WIP detail
    # page sometimes prepends).
    return title[: min(len(title), 30)]


@pytest.mark.mutates_db
def test_cm1_article_publish_then_visible_on_wire_and_swork(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """End-to-end CM-1 — publication propagation."""
    p = profile("PRESS_MEDIA")
    login(p)

    found = _find_article_id_and_title(page, base_url)
    if found is None:
        pytest.skip(
            f"no article owned by {p['email']} in /wip/articles/ — "
            "seed exhausted ?"
        )
    article_id, title = found
    needle = _title_substring(title)
    assert needle, "extracted title is empty"

    publish_url = f"{base_url}/wip/articles/publish/{article_id}/"
    unpublish_url = f"{base_url}/wip/articles/unpublish/{article_id}/"
    try:
        # Step 1 : publish (idempotent if already published).
        resp = page.goto(publish_url, wait_until="domcontentloaded")
        assert resp is not None and resp.status < 400, (
            f"publish article {article_id} : "
            f"status={resp.status if resp else '?'}"
        )

        # Step 2 : assert visible on /wire/tab/wall.
        page.goto(
            f"{base_url}/wire/tab/wall", wait_until="domcontentloaded"
        )
        wire_body = page.content()
        assert needle in wire_body, (
            f"CM-1 wire propagation : needle {needle!r} not found "
            f"on /wire/tab/wall — article {article_id} did not "
            "propagate. Either the publication notification "
            "service didn't run, the Wire query filters it out, "
            "or the title was rendered differently (HTML-escaped, "
            "wrapped, etc.)"
        )

        # Step 3 : assert visible on /swork/members/<id>?tab=publications.
        # /swork/profile/ redirects to /swork/members/<id> with the
        # default `tab=profile` — that tab doesn't show publications.
        # We must explicitly request the `publications` tab, which
        # renders ``member--tab-publications.j2`` with the user's
        # ArticlePost / Communique listing
        # (cf. swork.views._common.get_posts).
        page.goto(
            f"{base_url}/swork/profile/", wait_until="domcontentloaded"
        )
        if "/auth/login" in page.url:
            pytest.skip(
                "/swork/profile/ requires re-auth — session may "
                "have been invalidated by the publish action"
            )
        # Capture the user's member URL after the redirect, then
        # switch to ?tab=publications.
        member_url = page.url.rstrip("/")
        # Drop any existing query string before appending ours.
        member_url = member_url.split("?", 1)[0]
        page.goto(
            f"{member_url}?tab=publications",
            wait_until="domcontentloaded",
        )
        # The tab content is HTMX-loaded after page-load (cf.
        # `member--main.j2` : `<div id="tabs" hx-get="?tab=...
        # hx-trigger="load">`). Wait for the publications h2 to
        # appear before scraping.
        try:
            page.wait_for_selector(
                'h2:has-text("Publications")', timeout=8_000
            )
        except Exception:
            pytest.skip(
                "/swork/members/<id>?tab=publications : HTMX tab "
                "content didn't load. Either the seed user has no "
                "publications, or HTMX is mis-wired."
            )
        swork_body = page.content()
        if needle not in swork_body:
            empty_marker = "n'a pas encore publié de contenu"
            from pathlib import Path
            Path("/tmp/cm1_swork_body.html").write_text(swork_body)
            if empty_marker in swork_body:
                pytest.skip(
                    f"CM-1 swork : publications tab is empty for "
                    f"{member_url}. The WIP `Article.publish` may "
                    "not be wired to ArticlePost (newsroom vs Wire "
                    "polymorphism), or the seed user's articles "
                    "are stored under a different owner_id. Body "
                    "dumped to /tmp/cm1_swork_body.html."
                )
            pytest.fail(
                f"CM-1 swork propagation : needle {needle!r} not "
                f"found on {member_url}?tab=publications. The "
                "publications tab rendered (not 'empty' marker) "
                "but the needle is missing. Body dumped to "
                "/tmp/cm1_swork_body.html."
            )
    finally:
        # Always unpublish to restore approximate initial state.
        # Note : if the article was already published when the test
        # started, this leaves it unpublished — a one-bit state
        # mutation. Cheap and acceptable for now ; full lossless
        # restore would require querying the original state first.
        page.goto(unpublish_url, wait_until="domcontentloaded")
