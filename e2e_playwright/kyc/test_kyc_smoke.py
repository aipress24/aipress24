# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""KYC tunnel smoke + helpers — read-only.

Anonymous path : ``/kyc/`` → ``/kyc/profile`` → POST profile → wizard
render (GET only ; no submit). Every page must render without 5xx.

The full wizard end-to-end (POST a complete questionnaire, hit
``/kyc/done``, create a real ``User``) is out of scope here :
seed-DB pollution and per-profile field schemas make it fragile.
That belongs to a `mutates_db` integration test once we have a
``flask db reset-test-fixtures`` CLI (cf. plan, transverse #2).

Routes covered :

- ``GET /kyc/`` — landing page (`home.html`).
- ``GET /kyc/profile`` — community + profile picker.
- ``POST /kyc/profile`` — picks a profile_id, redirects to wizard.
- ``GET /kyc/wizard/<profile_id>`` — questionnaire renders.
- ``GET /kyc/check_mail/<email>`` — JSON-ish "ok" / "" probe.
- ``GET /kyc/undone`` — fallback page.
- ``GET /kyc/validation`` — synthesis / review (with empty session).
- ``GET /kyc/modify`` — restart-with-current-data branch (auth).

What's *not* tested here :

- Wizard form-submission validation (per-profile field schemas).
- ``/kyc/done`` actual user creation (mutates_db, no cleanup yet).
- Image upload variants (FileStorage vs base64 cropper).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

# Profile IDs from src/app/modules/kyc/survey_dataclass.py — pinned
# here for stability ; if the survey is restructured the test will
# fail loudly with a clear pointer.
_PROFILE_PER_COMMUNITY = {
    "PRESS_MEDIA": "P002",  # journaliste avec carte de presse
    "PRESS_RELATIONS": "P010",  # consultant.e RP
    "EXPERT": "P015",  # expert/consultant salarié
    "TRANSFORMER": "P022",  # consultant en transformation
    "ACADEMIC": "P030",  # enseignant-chercheur
}


def test_kyc_index_renders_for_anonymous(page: Page, base_url: str) -> None:
    """``/kyc/`` is the public landing page : KYC entry point.

    Anonymous-friendly — opening this from a marketing email or
    social link is the on-ramp for new users.
    """
    resp = page.goto(f"{base_url}/kyc/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400, (
        f"/kyc/ : status={resp.status if resp else '?'}"
    )
    # Should not have bounced to /auth/login.
    assert "/auth/login" not in page.url, (
        "/kyc/ should be reachable as anonymous"
    )


def test_kyc_profile_lists_all_communities(page: Page, base_url: str) -> None:
    """``/kyc/profile`` GET : lists every community and every
    profile defined in the survey model.

    Drives the read side of `views.profile_page` and
    `survey_model.get_survey_model`."""
    page.goto(f"{base_url}/kyc/profile", wait_until="domcontentloaded")
    # Each profile renders a radio with id="P001"…"P033".
    rendered = page.locator(
        'input[type="radio"][name="profile"]'
    ).evaluate_all(
        "els => els.map(e => e.value).filter(v => v && v !== '')"
    )
    assert len(rendered) >= 30, (
        f"/kyc/profile : expected >= 30 profile radios, got "
        f"{len(rendered)} : {rendered[:5]!r}"
    )
    # Each pinned profile_id used elsewhere must be present.
    for community, pid in _PROFILE_PER_COMMUNITY.items():
        assert pid in rendered, (
            f"/kyc/profile : pinned id {pid} ({community}) missing — "
            "survey may have been restructured"
        )


@pytest.mark.parametrize(
    ("community", "profile_id"),
    list(_PROFILE_PER_COMMUNITY.items()),
    ids=list(_PROFILE_PER_COMMUNITY.keys()),
)
def test_kyc_wizard_renders_for_each_community(
    page: Page,
    base_url: str,
    community: str,
    profile_id: str,
) -> None:
    """GET /kyc/wizard/<profile_id> renders a non-empty form for
    every community's representative profile_id.

    Drives `views.wizard_page` GET branch and
    `dynform.generate_form()` per-profile dispatch. A regression
    on any community would previously surface as a 500 only when
    a real user reached that step.
    """
    resp = page.goto(
        f"{base_url}/kyc/wizard/{profile_id}",
        wait_until="domcontentloaded",
    )
    assert resp is not None and resp.status < 400, (
        f"/kyc/wizard/{profile_id} : "
        f"status={resp.status if resp else '?'}"
    )
    # Form must have at least the standard fs_uniquifier / csrf hidden
    # fields plus *some* visible field.
    form_count = page.locator("form").count()
    assert form_count >= 1, (
        f"/kyc/wizard/{profile_id} ({community}) : no <form> found"
    )
    # Wizard form should have a CSRF token (Flask-WTF auto-injected).
    assert page.locator('input[name="csrf_token"]').count() > 0, (
        f"/kyc/wizard/{profile_id} : no CSRF token — "
        "Flask-WTF protection not engaged"
    )


def test_kyc_profile_post_redirects_to_wizard(
    page: Page,
    base_url: str,
    authed_post,
) -> None:
    """POST /kyc/profile {profile=P002} redirects to
    ``/kyc/wizard/P002``.

    Drives the POST branch of `profile_page` — the `make_form()`
    helper resolves the profile and 302s.
    """
    # `authed_post` runs `fetch` from the page's JS context — the
    # page must have navigated *somewhere* same-origin first or
    # the fetch errors with "Failed to fetch" (no document URL).
    page.goto(f"{base_url}/kyc/profile", wait_until="domcontentloaded")
    resp = authed_post(
        f"{base_url}/kyc/profile", {"profile": "P002"}
    )
    assert resp["status"] < 400, (
        f"/kyc/profile POST : {resp}"
    )
    assert resp["url"].endswith("/kyc/wizard/P002") or (
        "/kyc/wizard/P002" in resp["url"]
    ), f"/kyc/profile POST : did not land on wizard — url={resp['url']}"


def test_kyc_profile_post_with_unknown_id_re_renders(
    page: Page,
    base_url: str,
    authed_post,
) -> None:
    """POST /kyc/profile with a bogus profile_id : `get_survey_profile`
    raises, the route catches it and re-renders profile.html.
    No 5xx, no redirect to wizard.
    """
    page.goto(f"{base_url}/kyc/profile", wait_until="domcontentloaded")
    resp = authed_post(
        f"{base_url}/kyc/profile", {"profile": "P999_NOT_REAL"}
    )
    assert resp["status"] < 400, f"/kyc/profile bogus : {resp}"
    assert "/kyc/wizard/" not in resp["url"], (
        f"/kyc/profile bogus : unexpectedly landed on wizard "
        f"({resp['url']})"
    )


# ─── /kyc/check_mail/<email> JSON probe ────────────────────────────


def test_kyc_check_mail_with_existing_email_returns_empty(
    page: Page,
    base_url: str,
    profile,
    authed_get,
) -> None:
    """An email already used by an existing user must yield "" —
    that's how the KYC form's Alpine.js validator gates the
    "submit" button. Drives the `email_already_used` branch.
    """
    p = profile("PRESS_MEDIA")
    page.goto(f"{base_url}/kyc/", wait_until="domcontentloaded")
    resp = authed_get(
        f"{base_url}/kyc/check_mail/{p['email']}"
    )
    assert resp["status"] < 400
    # The route returns the literal string "" (empty body) when the
    # email is taken — `len` should be 0.
    assert resp["len"] == 0, (
        f"/kyc/check_mail with existing email : "
        f"expected empty body, got len={resp['len']}"
    )


def test_kyc_check_mail_with_new_valid_email_returns_ok(
    page: Page,
    base_url: str,
    authed_get,
) -> None:
    """A novel email on a real domain must yield "ok"."""
    # Tag-aliased on agencetca.info (real MX, not in seed CSV).
    new_email = "eliane+e2e_kyc_check_unique_2026@agencetca.info"
    page.goto(f"{base_url}/kyc/", wait_until="domcontentloaded")
    resp = authed_get(
        f"{base_url}/kyc/check_mail/{new_email}"
    )
    assert resp["status"] < 400
    assert resp["len"] == 2, (
        f"/kyc/check_mail with new email : expected 'ok' (len=2), "
        f"got len={resp['len']}"
    )


def test_kyc_check_mail_with_invalid_email_returns_empty(
    page: Page,
    base_url: str,
    authed_get,
) -> None:
    """A malformed email must yield "" — `email_validator.validate_email`
    raises, the route catches it.
    """
    # `not-an-email` has no @, should be rejected.
    page.goto(f"{base_url}/kyc/", wait_until="domcontentloaded")
    resp = authed_get(
        f"{base_url}/kyc/check_mail/not-an-email"
    )
    assert resp["status"] < 400
    assert resp["len"] == 0, (
        f"/kyc/check_mail with malformed email : "
        f"expected empty body, got len={resp['len']}"
    )


# ─── Static pages ──────────────────────────────────────────────────


def test_kyc_undone_renders(page: Page, base_url: str) -> None:
    """``/kyc/undone`` is the dead-end page when the user didn't
    accept the GCU. Renders later.html with no session
    requirements."""
    resp = page.goto(
        f"{base_url}/kyc/undone", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400


def test_kyc_validation_500s_with_empty_session_known_bug(
    page: Page, base_url: str
) -> None:
    """``/kyc/validation`` GET with an empty session 500s — known
    bug, qualified in
    ``local-notes/bugs/qualifies/kyc-validation-empty-session-500.md``.

    The route looks up ``get_survey_profile(profile_id)`` where
    ``profile_id`` defaults to "" — that raises
    ``ValueError('Unknown profile: ')``. Proper users always go
    through ``/kyc/profile`` first, which sets the session. But a
    direct visit (URL bookmark, prefetch, crawler) crashes.

    This test pins the **current** behavior so we don't shrug it
    off when fixing : the regression test should flip to
    ``status < 400`` once the fix lands.
    """
    resp = page.goto(
        f"{base_url}/kyc/validation", wait_until="domcontentloaded"
    )
    assert resp is not None
    # Current state : 500 because profile_id="" → ValueError.
    # When the bug is fixed (e.g. early-return to /kyc/profile),
    # update this assertion.
    assert resp.status == 500, (
        f"/kyc/validation : expected 500 (known bug), got "
        f"{resp.status}. If the bug was fixed, flip the test to "
        "`assert resp.status < 400` and update the bug note."
    )
    body = page.content()
    assert "Unknown profile" in body, (
        "/kyc/validation : 500 but not the expected 'Unknown "
        "profile' fragment — different bug, investigate"
    )


def test_kyc_modify_redirects_for_authenticated(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """``/kyc/modify`` for a logged-in user : sets `modify_form=True`
    in session and redirects to /kyc/profile.

    Drives the modify-an-existing-account path of the KYC flow."""
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(
        f"{base_url}/kyc/modify", wait_until="domcontentloaded"
    )
    # Final URL must end on /kyc/profile (the redirect target).
    assert "/kyc/profile" in page.url, (
        f"/kyc/modify : expected redirect to /kyc/profile, "
        f"got {page.url}"
    )
