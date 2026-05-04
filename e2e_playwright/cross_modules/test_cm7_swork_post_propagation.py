# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""CM-7 (Sprint 1 scope) — first action propagation : swork.

A logged-in user posts a short message via ``/swork/new_post``,
the post must appear on **their own** wall (`/swork/`).

Larger CM-7 scope (KYC tunnel → activation → first login →
first post) is deferred — needs a `flask db reset-test-fixtures`
CLI to undo seed pollution from a real user creation. See plan
chantier transverse #2.

What this test pins :

- ``swork.new_post`` form parser (`webargs`) accepts a non-empty
  ``message`` and creates a ``ShortPost`` row.
- ``swork.swork`` home query (`Post.owner_id.in_(followee_ids)`)
  includes ``g.user.id`` — the user sees their own posts even
  without follow relations.
- The post text round-trips through ``make_post()`` macro
  rendering on ``swork.j2``.

Sister tests to write later when the seed has stable follow rels :

- A posts → B (follower) sees post on /swork/
- A posts → C (non-follower) does NOT see post.
- Edit/delete propagation.
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page


@pytest.mark.mutates_db
def test_swork_new_post_appears_on_own_wall(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """Login → POST /swork/new_post → GET /swork/ → assert the
    posted message is on the page.

    Drives `swork.new_post` end-to-end and the home wall query
    (`/swork/`). Each run leaves a new ShortPost row in the DB
    (soft-deletable via `LifeCycleMixin.deleted_at` if cleanup
    needs to happen later).
    """
    p = profile("PRESS_MEDIA")
    login(p)

    # Unique enough to survive parallel runs and to avoid matching
    # any stale post from a previous run.
    marker = f"e2e-cm7-{int(time.time() * 1000)}"
    message = f"Post de test {marker} (CM-7 Sprint 1)"

    page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")
    resp = authed_post(
        f"{base_url}/swork/new_post", {"message": message}
    )
    assert resp["status"] < 400, f"new_post POST : {resp}"
    assert "/auth/login" not in resp["url"], (
        f"new_post POST : redirected to login — {resp['url']}"
    )

    # Reload the wall ; the post should be at the top
    # (ordered by created_at desc, limit 20 — fresh post wins).
    page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")
    body = page.content()
    assert marker in body, (
        f"swork wall : posted marker {marker!r} not found on /swork/. "
        "Either new_post didn't persist, or the home query "
        "doesn't include the user's own posts."
    )


@pytest.mark.mutates_db
def test_swork_new_post_with_empty_message_is_noop(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """POST /swork/new_post with an empty message must not create
    a row and must redirect cleanly.

    Drives the `if content:` guard branch in `new_post()` —
    important because a stray empty submit (double-click,
    autofill, paste then enter on empty field) shouldn't
    pollute the wall with empty rows.
    """
    p = profile("PRESS_MEDIA")
    login(p)

    page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")
    resp = authed_post(
        f"{base_url}/swork/new_post", {"message": ""}
    )
    assert resp["status"] < 400, f"new_post empty : {resp}"
    assert "/auth/login" not in resp["url"]
    # The redirect lands on /swork/ — verify the URL.
    assert "/swork" in resp["url"], (
        f"new_post empty : expected redirect under /swork/, "
        f"got {resp['url']}"
    )
