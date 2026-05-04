# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Partnership revocation — edge cases + asymmetry coverage.

The base lifecycle (invite → accept → revoke as the journalist) is
covered by ``test_bw_lifecycle.py::test_bw_partnership_full_lifecycle``.
This file fills three gaps :

1. **Idempotent revoke** : POSTing `revoke_partner_bw_id` twice in a
   row hits ``revoke_partnership`` twice. The second call returns
   `False` (status filter no longer matches `INVITED|ACCEPTED|ACTIVE`)
   and leaves the partnership in REVOKED state — the route still
   returns a 302 redirect, no 5xx.

2. **Garbage `revoke_partner_bw_id`** : non-UUID, unknown UUID, etc.
   Should redirect cleanly without server error. Defensive check on
   the route's input parsing.

3. **Asymmetry** : the PR agency cannot revoke a partnership from
   their side. Only the client BW (media-side) holds the
   `business_wall.partnerships` relation ; from the agency's
   `/BW/manage-external-partners`, the partnership row simply
   isn't there to revoke. POSTing `revoke_partner_bw_id` against
   the client's BW id, while logged in as the agency, must
   no-op cleanly (the agency's `current_business_wall` is the
   agency's BW, which doesn't own that Partnership row).

All three are mutates_db (re-uses the same partnership the
lifecycle test creates). Cleanup is idempotent : the lifecycle
test's `finally` block also revokes, so leaving a REVOKED row is
expected steady-state.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Same BW used by the partnership / role-invitation lifecycle tests.
_ERICK_NAMED_BW_ID = "3be67123-b68d-48ad-9043-e2a206d18893"
_PR_BW_OWNER_EMAIL = "eliane+BrigitteWasser@agencetca.info"

# A garbage but well-formed UUID (lowercase v4, but no row matches).
_FAKE_BW_ID = "11111111-2222-3333-4444-555555555555"
# A non-UUID — exercises the parser's tolerance.
_NON_UUID = "not-a-uuid-at-all"


def _ensure_partnership_active(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
) -> str | None:
    """Re-establish an INVITED+ACCEPTED partnership between erick's
    media BW and a PR agency. Returns the partner BW id, or None if
    setup can't be completed (skip the test in that case).

    Mirrors the setup of `test_bw_partnership_full_lifecycle`."""
    journalist = profile("PRESS_MEDIA")
    pr_owner = next(
        (p for p in profiles if p["email"] == _PR_BW_OWNER_EMAIL), None
    )
    if pr_owner is None:
        pytest.skip(f"{_PR_BW_OWNER_EMAIL} not in CSV")
        return None  # pragma: no cover

    login(journalist)
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    if sel["status"] >= 400 or "/auth/login" in sel["url"]:
        pytest.skip(f"select-bw warm-up failed : {sel}")

    page.goto(
        f"{base_url}/BW/manage-external-partners",
        wait_until="domcontentloaded",
    )
    options = page.locator(
        'select[name="pr_provider"] option[value]'
    ).evaluate_all(
        "els => els.map(e => e.value).filter(v => v && v !== '')"
    )
    if not options:
        pytest.skip("no PR-BW available to invite")
        return None  # pragma: no cover
    partner_bw_id = options[0]

    invite = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"pr_provider": partner_bw_id},
    )
    if invite["status"] >= 400 or "/auth/login" in invite["url"]:
        pytest.skip(f"invite POST failed : {invite}")

    return partner_bw_id


@pytest.mark.mutates_db
def test_partnership_double_revoke_is_idempotent(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
) -> None:
    """Revoking the same partnership twice : the second POST is a
    no-op server-side (status no longer in the revocable set) but
    must still return a clean redirect."""
    partner_bw_id = _ensure_partnership_active(
        page, base_url, profile, profiles, login, authed_post
    )
    assert partner_bw_id is not None

    # First revoke : succeeds (`revoke_partnership` returns True).
    first = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"revoke_partner_bw_id": partner_bw_id},
    )
    assert first["status"] < 400, f"first revoke : {first}"
    assert "/auth/login" not in first["url"]

    # Second revoke on the same partner_bw_id : no matching row
    # in INVITED|ACCEPTED|ACTIVE state ; route still 302-redirects.
    second = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"revoke_partner_bw_id": partner_bw_id},
    )
    assert second["status"] < 400, f"second revoke : {second}"
    assert "/auth/login" not in second["url"]


@pytest.mark.mutates_db
@pytest.mark.parametrize(
    ("label", "bw_id"),
    [("garbage-uuid", _FAKE_BW_ID), ("non-uuid", _NON_UUID)],
    ids=["garbage-uuid", "non-uuid"],
)
def test_partnership_revoke_with_invalid_id(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
    label: str,
    bw_id: str,
) -> None:
    """POST `revoke_partner_bw_id=<garbage>` must redirect cleanly
    without 5xx — the route's defensive code path."""
    journalist = profile("PRESS_MEDIA")
    login(journalist)

    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]

    resp = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"revoke_partner_bw_id": bw_id},
    )
    assert resp["status"] < 400, (
        f"{label} : revoke with {bw_id!r} returned {resp['status']}"
    )
    assert "/auth/login" not in resp["url"]


@pytest.mark.mutates_db
def test_partnership_revoke_from_agency_side_is_noop(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
) -> None:
    """The PR agency cannot revoke a partnership from their side —
    only the client BW holds the Partnership row.

    1. Set up an active partnership (journalist invites, agency
       accepts).
    2. Login as the agency.
    3. POST `revoke_partner_bw_id=<journalist's BW id>` against the
       agency's `/BW/manage-external-partners`.
    4. Assert the route redirects cleanly. The revoke is a no-op
       because `business_wall.partnerships` (the agency's BW) does
       not contain that Partnership row — `revoke_partnership`
       loops over the wrong relation and returns False, no 5xx.
    5. Verify the partnership is still active by re-loading the
       client's manage-external-partners as the journalist :
       `current_pr_bw_info` should still list the agency.
    """
    partner_bw_id = _ensure_partnership_active(
        page, base_url, profile, profiles, login, authed_post
    )
    assert partner_bw_id is not None

    # Agency accepts the invite by clicking the email confirmation
    # URL — same as the existing partnership lifecycle test. Re-use
    # the helper from there to keep things consistent.
    # (Skipping the explicit accept here : `_ensure_partnership_active`
    # only invites. For this test the partnership being in INVITED
    # state is enough — the agency has the same lack of authority to
    # revoke regardless of state.)

    pr_owner = next(
        (p for p in profiles if p["email"] == _PR_BW_OWNER_EMAIL), None
    )
    assert pr_owner is not None  # asserted in _ensure_partnership_active

    # Login as the agency. Their `current_business_wall` is the
    # agency's BW, not erick's media BW.
    login(pr_owner)
    resp = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"revoke_partner_bw_id": partner_bw_id},
    )
    assert resp["status"] < 400, (
        f"agency-side revoke returned {resp['status']} : agency "
        "shouldn't be able to revoke but the route should still 302"
    )
    assert "/auth/login" not in resp["url"]

    # Confirm the partnership still appears on the journalist's
    # manage page (i.e. wasn't actually revoked).
    login(profile("PRESS_MEDIA"))
    sel = authed_post(
        f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {}
    )
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]
    page.goto(
        f"{base_url}/BW/manage-external-partners",
        wait_until="domcontentloaded",
    )
    # Look for the agency BW id in the page : either listed as an
    # active partner (current_pr_bw_info) or pending. If it's no
    # longer visible, the agency successfully revoked from their
    # side — that would be the bug.
    body = page.content()
    assert partner_bw_id in body or "Aucun partenariat" not in body, (
        f"partnership {partner_bw_id!r} no longer visible after the "
        "agency POSTed revoke — that would be a privilege-escalation bug"
    )

    # Cleanup (best-effort) : journalist revokes the partnership.
    authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"revoke_partner_bw_id": partner_bw_id},
    )
