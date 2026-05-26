# ruff: noqa: INP001, PT018, PT007
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests — Trello tickets #0095 → #0128.

Bugs covered :
- **#0095** — Taxonomies : trim whitespace sur le select type
  d'organisation (commits `0a0c2ab8` + migration `a1c3f8b0e5d2`).
- **#0107** — `metier_fonction_for_bw` per-BW-type priority — form
  pre-fill non-empty pour un journaliste media.
- **#0109 part 1** — BW header logo must not carry ``hx-boost``,
  full page navigation re-runs Alpine init (Wire feed photos).
- **#0112** — rights-policy uses checkboxes for media BWs, not a
  textarea of raw IDs.
- **#0118** — events filter from user A purged before user B sees
  ``/events`` (signal handler ``_clear_per_user_session_state``).
- **#0122** — confirm-partnership page exposes « Gérer mes Business
  Walls » + « Retour à la plateforme » CTAs.
- **#0126** — SOCIAL right-column sticky has `max-h-[80vh]` +
  `overflow-y-auto`.
- **#0128** — communiqué « Voir » page renders the same Alpine
  carousel as NEWS (was: form fields only, no images).
"""

from __future__ import annotations

import re

import pytest
from _shared import _COMM_PAT, _PRESS_MEDIA, _PRESS_RELATIONS, _first_id_in_table
from playwright.sync_api import Page

# ─── #0095 ─────────────────────────────────────────────────────────


def test_bug_0095_taxonomies_no_whitespace_dupes(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """Bug #0095 — Le select « Type de votre organisation » sur
    ``/BW/configure-content`` ne doit pas avoir de catégorie
    fantôme avec espaces parasites (ex: ``ORGANISATIONS PRIVÉES ``
    avec espace final, qui apparaissait dupliquée à côté de la
    vraie catégorie).

    Le fix (commit `0a0c2ab8` + migration `a1c3f8b0e5d2`) :
    1. trim défensif sur `tax_taxonomy.{name,category,value}` dans
       `taxonomies/_service.py:create_entry`/`update_entry`.
    2. migration qui clean les rows existants.

    On vérifie via ``/BW/configure-content`` qui rend le select.
    Le user PRESS_MEDIA doit avoir un BW actif — on selectionne le
    BW erick utilisé partout dans les tests bw lifecycle.
    """
    # Erick has 3 BWs ; the named one used by lifecycle tests.
    erick_bw_id = "3be67123-b68d-48ad-9043-e2a206d18893"
    p = profile(_PRESS_MEDIA)
    login(p)
    # Need a navigated page before authed_post.
    page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
    if "/BW/confirm-subscription" in page.url:
        pytest.skip(f"{p['email']} has no BW — can't reach configure-content")
    # /BW/select-bw/<id> is POST-only.
    sel = authed_post(f"{base_url}/BW/select-bw/{erick_bw_id}", {})
    if sel["status"] >= 400 or "/auth/login" in sel["url"]:
        pytest.skip(f"select-bw failed : {sel}")
    page.goto(
        f"{base_url}/BW/configure-content",
        wait_until="domcontentloaded",
    )
    if "/BW/configure-content" not in page.url:
        pytest.skip(
            f"{p['email']} can't reach /BW/configure-content — landed on {page.url}"
        )
    body = page.content()

    # Look for any optgroup or option with a trailing space in
    # its label — this is the corruption pattern.
    # Pattern : <optgroup label="ORGANISATIONS PRIVÉES "> (with
    # trailing space before the closing quote).
    bad_optgroup = re.search(r'<optgroup\s+label="[^"]+ "', body)
    assert bad_optgroup is None, (
        f"BW configure-content : optgroup label with trailing "
        f"space found ({bad_optgroup.group(0)!r}) — bug #0095 "
        "trim defense regressed."
    )
    bad_option = re.search(r'<option\s+[^>]*value="[^"]+ "', body)
    assert bad_option is None, (
        f"BW configure-content : option value with trailing "
        f"space found ({bad_option.group(0)!r}) — bug #0095 "
        "trim defense regressed."
    )


# ─── #0107 ─────────────────────────────────────────────────────────


def test_bug_0107_bw_pre_fill_uses_metier_fonction_for_bw(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """Bug #0107 — Le form `nominate-contacts` (BW activation step
    2) pré-remplit `owner_title` depuis
    ``user.metier_fonction_for_bw(bw_type)``, qui choisit la
    fonction selon le type de BW (Media → fonctions journalisme
    prioritaires) plutôt que de toujours retomber sur
    ``metiers[0]``.

    Couverture principale : 6 unit tests dans
    `tests/a_unit/models/test_auth.py`. Ici on vérifie l'intégration
    end-to-end : un journaliste qui démarre l'activation d'un BW
    media voit `owner_title` non-vide et **différent** de la
    string vide qui résultait du fallback `metiers[0]` quand
    `metiers` était vide.

    Walk : login wizard user → POST select-subscription/media →
    GET nominate-contacts → assert input[name=owner_title] has a
    non-empty value attribute.

    Skip-condition note : the test needs a user who is BOTH a
    journalist (with `fonctions_journalisme` / `metiers` data,
    so `metier_fonction_for_bw('media')` returns non-empty) AND
    has no active BW yet (so they can drive the « first
    activation » path). The default `PRESS_MEDIA` seed user
    (erick) satisfies the first but already has BWs ; the
    « wizard guinea-pig » (AliMbappe) satisfies the second but
    is a PR-agency profile with no journalism data. No seed
    user fits both — hence the skip below remains structural.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
    if "/BW/dashboard" in page.url or "/BW/select-bw" in page.url:
        # User has BW(s) ; select-subscription would error out.
        # Skip — the wizard pre-fill is only on first activation.
        pytest.skip(
            f"{p['email']} already has a BW — pre-fill path not exercised on this run"
        )
    # Confirm bw_type=media to unlock nominate-contacts.
    sel = authed_post(f"{base_url}/BW/select-subscription/media", {})
    if sel["status"] >= 400 or "/auth/login" in sel["url"]:
        pytest.skip(f"select-subscription failed : {sel}")

    page.goto(
        f"{base_url}/BW/nominate-contacts",
        wait_until="domcontentloaded",
    )
    if "/BW/nominate-contacts" not in page.url:
        pytest.skip(f"can't reach /BW/nominate-contacts — landed on {page.url}")
    # The form has <input name="owner_title" value="...">. Read
    # the value.
    try:
        title_value = page.locator('input[name="owner_title"]').first.input_value(
            timeout=2_000
        )
    except Exception:
        title_value = ""
    # Pre-fix : value would often be a "metiers[0]" misleading
    # function. Post-fix : non-empty + journalism-context for
    # PRESS_MEDIA users.
    # Note : we only assert non-empty here. The exact value
    # depends on the user's KYC profile data.
    assert title_value, (
        f"nominate-contacts : owner_title pre-fill is empty for "
        f"{p['email']} — `metier_fonction_for_bw('media')` likely "
        "returned empty string, suggesting both fonctions_journalisme "
        "and metiers are empty for this user. Bug #0107 fix may "
        "have regressed (or seed user lost their journalism "
        "profile data)."
    )


# ─── #0109 part 1 ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    (
        "/BW/",
        "/BW/dashboard",
        "/BW/manage-internal-roles",
    ),
)
def test_bug_0109_bw_header_logo_does_not_use_hxboost(
    page: Page, base_url: str, profile, login, path: str
) -> None:
    """Bug #0109 part 1 — when the user clicked the AiPRESS24 logo from
    a BW configuration page, htmx-boost swapped the body without re-running
    Alpine init. The destination wire feed renders article carousels via
    Alpine; the swapped components stayed `display: none` because `x-init`
    never fired. Result: user landed on the news page with no photos until
    they hit refresh.

    Fix: drop `hx-boost` from the BW header's logo `<a>`. Click = full
    page navigation = Alpine init runs normally. The performance loss is
    one extra page-load on a navigation that's exit-from-the-tunnel
    anyway — totally fine.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}{path}", wait_until="domcontentloaded")
    if resp is None or resp.status >= 400:
        pytest.skip(f"{path} not accessible : {resp.status if resp else '?'}")
    has_hxboost = page.evaluate(
        """() => {
            const imgs = document.querySelectorAll('img[alt="Aipress24"]');
            for (const img of imgs) {
                const a = img.closest('a');
                if (!a) continue;
                if (a.hasAttribute('hx-boost')) return true;
            }
            return false;
        }"""
    )
    assert not has_hxboost, (
        f"BW header logo on {path} carries `hx-boost` — bug "
        "#0109 part 1 regression. The destination Alpine-driven "
        "wire feed needs a full page reload, not an htmx swap."
    )


# ─── #0112 ────────────────────────────────────────────────────────


def test_bug_0112_rights_policy_has_media_picker(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """Bug #0112 — Le configurateur de cession de droits utilisait un
    textarea pour coller les IDs BW (non ergonomique). Le fix le
    remplace par une liste de checkboxes des BW for Media actifs.

    Vérifie que la page affiche des checkboxes (pas un textarea) et
    qu'au moins un média est listé.
    """
    # Select Erick's media BW to ensure the rights-policy card is visible.
    p = profile(_PRESS_MEDIA)
    erick_bw_id = "3be67123-b68d-48ad-9043-e2a206d18893"
    login(p)
    page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
    if "/BW/dashboard" in page.url or "/BW/select-bw" in page.url:
        sel = authed_post(f"{base_url}/BW/select-bw/{erick_bw_id}", {})
        if sel["status"] >= 400 or "/auth/login" in sel["url"]:
            pytest.skip(f"select-bw failed : {sel} — can't reach rights-policy")

    resp = page.goto(f"{base_url}/BW/rights-policy", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400

    # Post-fix : must have checkboxes, NOT a textarea
    has_checkboxes = (
        page.locator('input[type="checkbox"][name="media_ids"]').count() > 0
    )
    has_textarea = page.locator('textarea[name="media_ids"]').count() > 0
    assert has_checkboxes and not has_textarea, (
        "rights-policy page should show checkboxes for media BWs, "
        f"not a textarea — bug #0112 regression. "
        f"checkboxes={has_checkboxes}, textarea={has_textarea}"
    )


# ─── #0118 ────────────────────────────────────────────────────────


@pytest.mark.mutates_db
def test_bug_0118_events_filter_does_not_leak_between_users(
    page: Page,
    base_url: str,
    profiles,
    login,
    authed_post,
) -> None:
    """Bug #0118 — events filter persistence. User A logs in, sets a
    filter on /events (writes to `session["events:state"]`), logs out.
    User B logs in on the same browser context. The filter from A must
    not be visible to B. Pinned in `app/flask/hooks.py:_clear_per_user_session_state`."""
    pool = [
        p
        for p in profiles
        if p["email"].startswith("erick") or p["email"].startswith("eliane")
    ]
    if len(pool) < 2:
        pytest.skip("not enough seed profiles for two-user scenario")
    user_a, user_b = pool[0], pool[1]

    login(user_a)
    page.goto(f"{base_url}/events", wait_until="domcontentloaded")
    set_state = page.evaluate(
        """async (url) => {
            const r = await fetch(url, {
                method: 'GET', credentials: 'same-origin',
                headers: {'HX-Request': 'true'},
            });
            return {status: r.status};
        }""",
        f"{base_url}/events?q=conference",
    )
    if set_state["status"] >= 400:
        pytest.skip(
            f"GET /events?q=... unavailable for {user_a['email']!r}: {set_state}"
        )
    cookies_a = page.context.cookies()
    assert cookies_a, "user A login didn't set a session cookie"

    page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
    login(user_b)

    page.goto(f"{base_url}/events", wait_until="domcontentloaded")
    q_value = page.evaluate(
        """() => {
            const el = document.querySelector('input[name="q"]');
            return el ? (el.value || '') : '';
        }"""
    )
    assert q_value == "", (
        "events filter from user A leaked to user B — session "
        "purge handler in hooks.py did not fire. Got "
        f"q={q_value!r} for {user_b['email']!r}."
    )


# ─── #0122 ────────────────────────────────────────────────────────


_ERICK_NAMED_BW_ID = "3be67123-b68d-48ad-9043-e2a206d18893"
_PR_BW_OWNER_EMAIL = "eliane+BrigitteWasser@agencetca.info"
_BRIGITTE_AGENCY_BW_ID = "662e153a-ab3b-4c52-994e-5b539f254589"
_CONFIRM_PARTNERSHIP_URL_RE = re.compile(
    r"http[s]?://[^/\s]+(/BW/confirm-partnership-invitation/"
    r"[a-f0-9-]+/[a-f0-9-]+)"
)


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_bug_0122_partnership_accepted_page_has_back_ctas(
    page: Page,
    base_url: str,
    profile,
    profiles,
    login,
    authed_post,
    mail_outbox,
) -> None:
    """Bug #0122 — confirm-partnership page had no explicit way back to
    the platform / BW management. Fix: two CTAs (« Gérer mes Business
    Walls » + « Retour à la plateforme ») inline in the success / refused
    card. End-to-end: trigger a partnership invite (CM-2 setup), agency
    accepts, then verify the two CTAs are present."""
    journalist = profile(_PRESS_MEDIA)
    pr_owner = next((p for p in profiles if p["email"] == _PR_BW_OWNER_EMAIL), None)
    if pr_owner is None:
        pytest.skip(f"{_PR_BW_OWNER_EMAIL} not in CSV")

    login(journalist)
    sel = authed_post(f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {})
    assert sel["status"] < 400 and "/auth/login" not in sel["url"]
    page.goto(
        f"{base_url}/BW/manage-external-partners",
        wait_until="domcontentloaded",
    )
    options = page.locator('select[name="pr_provider"] option[value]').evaluate_all(
        "els => els.map(e => e.value).filter(v => v && v !== '')"
    )
    if not options:
        pytest.skip("no PR-BW available for partnership")
    partner_bw_id = (
        _BRIGITTE_AGENCY_BW_ID if _BRIGITTE_AGENCY_BW_ID in options else options[0]
    )

    mail_outbox.reset()
    invite = authed_post(
        f"{base_url}/BW/manage-external-partners",
        {"pr_provider": partner_bw_id},
    )
    assert invite["status"] < 400 and "/auth/login" not in invite["url"]
    captured = mail_outbox.messages()
    if not captured:
        pytest.skip("partnership invitation mail not captured")
    confirm_path = next(
        (
            m.group(1)
            for body in (msg["body"] for msg in captured)
            if (m := _CONFIRM_PARTNERSHIP_URL_RE.search(body))
        ),
        None,
    )
    if confirm_path is None:
        pytest.skip("no confirmation URL in invitation mail body")

    login(pr_owner)
    try:
        accept = authed_post(f"{base_url}{confirm_path}", {"action": "accept"})
        assert accept["status"] < 400, accept

        page.goto(f"{base_url}{confirm_path}", wait_until="domcontentloaded")
        body = page.content()
        assert "Partenariat accepté" in body or "déjà été traitée" in body, (
            f"unexpected post-accept page content : {body[:300]!r}"
        )
        assert page.locator('[data-testid="back-to-bw"]').count() >= 1, (
            "missing « Gérer mes Business Walls » CTA on "
            "post-partnership-accept page — bug #0122 regression"
        )
        assert page.locator('[data-testid="back-to-platform-card"]').count() >= 1, (
            "missing « Retour à la plateforme » CTA on "
            "post-partnership-accept page — bug #0122 regression"
        )
        layout_buttons = page.locator('[data-testid="back-to-platform"]').count()
        assert layout_buttons >= 1, (
            "BW layout's `_back_to_platform.html` strip missing "
            "— bugs #0109/#0111/#0114 regression"
        )
    finally:
        login(journalist)
        authed_post(f"{base_url}/BW/select-bw/{_ERICK_NAMED_BW_ID}", {})
        authed_post(
            f"{base_url}/BW/manage-external-partners",
            {"revoke_partner_bw_id": partner_bw_id},
        )


# ─── #0126 ────────────────────────────────────────────────────────


def test_bug_0126_swork_right_column_scrollable(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Bug #0126 — Les modules de publicité en colonne de droite sur le
    wall SOCIAL sont trop étroits et trop longs. Le fix ajoute
    `max-h-[80vh] overflow-y-auto` au conteneur sticky.

    Vérifie que la colonne de droite a une hauteur limitée et une
    barre de défilement.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}/swork/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400

    # The sticky container should have max-h-[80vh] and overflow-y-auto
    has_scroll = page.evaluate(
        """() => {
            const aside = document.querySelector('aside[class*="lg:col-span-4"]');
            if (!aside) return false;
            const sticky = aside.querySelector('.sticky');
            if (!sticky) return false;
            const cls = sticky.className || '';
            return cls.includes('max-h-') && cls.includes('overflow-y-auto');
        }"""
    )
    assert has_scroll, (
        "SOCIAL wall right column : sticky container missing "
        "max-h-[80vh] or overflow-y-auto — bug #0126 regression"
    )


# ─── #0128 ────────────────────────────────────────────────────────


def test_bug_0128_communique_view_renders_image_gallery(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0128 — communiqué « Voir » must render the attached images,
    not just the form fields. Fix renders the same Alpine carousel used
    on the NEWS press-release page via the `_extra_view_html` hook on
    `CommuniquesWipView`. Asserts the gallery section header appears and
    at least one `<img>` is rendered."""
    p = profile(_PRESS_RELATIONS)
    login(p)
    cid = _first_id_in_table(page, f"{base_url}/wip/communiques/", _COMM_PAT)
    if cid is None:
        pytest.skip("no communiqué visible for PRESS_RELATIONS user")

    resp = page.goto(
        f"{base_url}/wip/communiques/{cid}/", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400
    body = page.content()
    if "Images" not in body:
        pytest.skip(f"communiqué {cid} has no images attached")
    img_count = page.locator("section img[src]").count()
    assert img_count > 0, "gallery section present but no <img> rendered"
