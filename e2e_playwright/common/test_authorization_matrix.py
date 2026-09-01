# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""URL-level authorization matrix (read-only).

Verifies that each community is hard-blocked at the URL level from
sections it should not access. The gates we rely on :

- ``/wip/newsroom`` → ``RoleEnum.PRESS_MEDIA`` only ; raises
  ``Forbidden`` for anyone else (`app/modules/wip/views/newsroom.py`).
- ``/wip/comroom``  → ``PRESS_RELATIONS | EXPERT | TRANSFORMER |
  ACADEMIC`` ; raises ``Forbidden`` for ``PRESS_MEDIA``
  (`app/modules/wip/views/comroom.py` +
  `app/modules/wip/pr_access.py`).
- ``/admin/``       → ``RoleEnum.ADMIN`` only ; the
  ``before_request`` on the admin blueprint raises
  ``Unauthorized``/``Forbidden`` for everyone else
  (`app/modules/admin/__init__.py`).

These three are the URL gates the rest of the suite (and the menu
visibility checks in ``test_communities.py``) depend on. Any
regression in role evaluation would be silent without these.

**How denial looks on the wire.** Since 2026-08-11
(`app/flask/hooks.py::handle_forbidden_error`) a `Forbidden` raised
by a *UI* page no longer reaches the browser as 403 : it is flashed
and redirected to `/`, which lands on the wall. Only `/api/` keeps
the bare 403. The gate is intact — asserting on the status alone was
not, and reported every one of these as an authorization regression.
The handler stamps ``X-Access-Denied: true`` on the redirect for
exactly this purpose, so that is what we look for.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Communities that must NOT be able to open Newsroom (anyone except
# PRESS_MEDIA).
NON_PRESS_MEDIA = ("PRESS_RELATIONS", "EXPERT", "TRANSFORMER", "ACADEMIC")

# Communities that MUST be denied /admin/ (everything except ADMIN ;
# we don't have an ADMIN test profile in the CSV).
ALL_COMMUNITIES = ("PRESS_MEDIA", *NON_PRESS_MEDIA)

# Forbidden status set : Flask-Security may surface 401 (Unauthorized)
# *or* 403 (Forbidden) depending on the gate's `abort()` choice.
# Still the shape for `/api/` and for anything that aborts before the
# error handler runs.
FORBIDDEN_STATUSES = {401, 403}

#: Posé par `handle_forbidden_error` sur la redirection qu'il rend.
_DENIED_HEADER = "x-access-denied"


def _was_denied(response) -> bool:
    """True when the app refused the page, however it said so.

    Either a forbidden status, or the redirect `handle_forbidden_error`
    issues — whose marker header sits on the 302, not on the page we
    finally land on, so walk back up the redirect chain.
    """
    if response.status in FORBIDDEN_STATUSES:
        return True
    request = response.request
    while request is not None:
        hop = request.response()
        if hop is not None and hop.headers.get(_DENIED_HEADER) == "true":
            return True
        request = request.redirected_from
    return False


@pytest.mark.parametrize("community", NON_PRESS_MEDIA, ids=NON_PRESS_MEDIA)
def test_newsroom_forbidden_for_non_press_media(
    page: Page,
    base_url: str,
    profile,
    login,
    community: str,
) -> None:
    """Only PRESS_MEDIA can reach /wip/newsroom."""
    p = profile(community)
    login(p)
    resp = page.goto(f"{base_url}/wip/newsroom", wait_until="domcontentloaded")
    assert resp is not None
    assert _was_denied(resp), (
        f"{community} ({p['email']}) should be denied on /wip/newsroom "
        f"but got {resp.status} at {resp.url}"
    )


def test_comroom_forbidden_for_press_media(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """PRESS_MEDIA must NOT reach /wip/comroom — Newsroom is theirs."""
    p = profile("PRESS_MEDIA")
    login(p)
    resp = page.goto(f"{base_url}/wip/comroom", wait_until="domcontentloaded")
    assert resp is not None
    assert _was_denied(resp), (
        f"PRESS_MEDIA ({p['email']}) should be denied on /wip/comroom "
        f"but got {resp.status} at {resp.url}"
    )


@pytest.mark.parametrize("community", ALL_COMMUNITIES, ids=ALL_COMMUNITIES)
def test_admin_forbidden_for_non_admin(
    page: Page,
    base_url: str,
    non_admin_profile,
    login,
    community: str,
) -> None:
    """A non-admin community member must be denied on /admin/.

    Uses `non_admin_profile` (not `profile`) so we don't accidentally
    pick a project-owner account that legitimately holds ADMIN in
    the local DB (`KNOWN_ADMIN_MAILBOXES` in conftest)."""
    p = non_admin_profile(community)
    login(p)
    resp = page.goto(f"{base_url}/admin/", wait_until="domcontentloaded")
    assert resp is not None
    assert _was_denied(resp), (
        f"{community} ({p['email']}) should be denied on /admin/ "
        f"but got {resp.status} at {resp.url}"
    )
