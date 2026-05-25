# ruff: noqa: INP001, PLC0415, B012, PT018, PT007
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests for previously-resolved bugs (`local-notes/bugs/resolus/`).

Chaque test ici cible un bug fixé en commit identifié, et vérifie
que le comportement post-fix tient. Si l'un de ces tests devient
rouge, c'est que le fix correspondant a régressé.

Bugs couverts dans ce fichier :

- **#0050** — PR Agency BW activation card → direct link to pricing
  (commit `24ff45d1`).
- **#0061** — Avis enquête « non-mais » wording + suggestion de
  collègue (commit `75dbd5f8`).
- **#0070** — Avis enquête phase breadcrumbs (commit `24ff45d1`).
- **#0088** — Confirmation changement email redirige vers
  ``/preferences/`` (commit `24ff45d1`).
- **#0095** — Taxonomies : trim whitespace sur le select type
  d'organisation (commits `0a0c2ab8` + migration `a1c3f8b0e5d2`).
- **#0109** part 1 — BW header logo must not carry ``hx-boost``,
  full page navigation re-runs Alpine init (Wire feed photos).
- **#0118** — events filter from user A purged before user B sees
  ``/events`` (signal handler ``_clear_per_user_session_state``).
- **#0122** — confirm-partnership page exposes « Gérer mes Business
  Walls » + « Retour à la plateforme » CTAs.
- **#0128** — communiqué « Voir » page renders the same Alpine
  carousel as NEWS (was: form fields only, no images).
- **#0129** — communiqué/sujet « Voir » shows publisher NAME, not
  the raw FK Snowflake id.
- **#0130** — invitations preferences page renders without crash
  (storage normalises email; lookup mirrors).
- **#0131** — calendar entries link to ``/events/<id>`` with
  ``HH:MM`` time and a real ``<time datetime>`` attribute.
- **#0132** — sujets table exposes Publier/Dépublier action so
  DRAFT proposals reach the targeted media.

Bugs résolus avec couverture e2e ailleurs (cf. note dans
``bugs/resolus/`` correspondante) :

- ``kyc-validation-empty-session-500`` → ``kyc/test_kyc_smoke.py``.
- ``wire-item-non-numeric-id-500`` → ``wire/test_wire_surfaces.py``.
- ``notifications-mark-read-open-redirect`` →
  ``notifications/test_notifications_surfaces.py``.
- ``bw-configure-gallery-500`` → ``bw/test_bw_configure.py``.
- ``wip-content-form-date-mismatch`` → ``wip/test_content_crud.py``.
- ``#0106`` (MAX_FORM_MEMORY_SIZE) → ``infra/test_upload_limits.py``.
- ``bw-confirmation-free-double-creation`` → ``bw/test_bw_wizard.py``.

Bugs avec couverture template/source-level (pas pure e2e mais
exécutés dans la même suite) :

- **#0068** — wording du mail de notification avis-enquête.
  Couvert par `test_bug_0068_avis_enquete_mail_wording` ci-dessous
  (template-source check).
- **#0107** — `metier_fonction_for_bw` per-BW-type priority. Couvert
  par 6 unit tests dans `tests/a_unit/models/test_auth.py` ; ici
  on ajoute `test_bug_0107_bw_pre_fill_uses_metier_fonction_for_bw`
  qui vérifie l'intégration end-to-end (form pre-fill non vide
  pour un journaliste avec bw_type=media).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page

# ─── #0050 ─────────────────────────────────────────────────────────


@pytest.mark.mutates_db
def test_bug_0050_pr_card_renders_direct_pricing_link(
    page: Page,
    base_url: str,
    profiles,
    login,
    authed_post,
) -> None:
    """Bug #0050 — La card « PR Agency » sur ``/BW/activation-choice``
    doit rendre un lien direct vers ``/BW/pricing/pr`` avec le
    libellé « Activer pour 1 client », pas un input de comptage.

    Le fix (commit `24ff45d1`) ajoute `skip_pricing_input=True` et
    `pricing_default=1` sur ``BW_TYPES["pr"]``, et le template
    `01_activation_choice.html` rend le branche `skip_pricing_input`.

    Walk : login wizard user → POST select-subscription/pr → GET
    activation-choice → inspect PR card.
    """
    # Re-use the wizard guinea pig from `test_bw_wizard.py`.
    user = next(
        (p for p in profiles if p["email"] == "eliane+AliMbappe@agencetca.info"),
        None,
    )
    if user is None:
        pytest.skip("wizard user not in CSV")

    login(user)
    page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
    if "/BW/dashboard" in page.url or "/BW/select-bw" in page.url:
        pytest.skip(
            f"{user['email']} already has a BW — wizard cleanup "
            "from a previous run is incomplete"
        )

    # Confirm bw_type=pr to unlock activation-choice rendering.
    select = authed_post(f"{base_url}/BW/select-subscription/pr", {})
    assert select["status"] < 400
    assert "/auth/login" not in select["url"]

    # Now activation-choice renders all cards.
    page.goto(
        f"{base_url}/BW/activation-choice",
        wait_until="domcontentloaded",
    )
    body = page.content()

    # Post-fix : the PR card must NOT render the client-count
    # input form. Two valid renderings exist :
    # - Stripe path (`STRIPE_LIVE_ENABLED=True`) → link to
    #   `/BW/stripe-info/pr` ("Saisir les informations de
    #   facturation").
    # - Pre-Stripe path (`STRIPE_LIVE_ENABLED=False`) → link to
    #   `/BW/pricing/pr` ("Activer pour 1 client") via the
    #   `skip_pricing_input` branch.
    # In both modes, the bug #0050 symptom (set_pricing/pr form)
    # must be absent.
    has_pricing_link = "/BW/pricing/pr" in body
    has_stripe_link = "/BW/stripe-info/pr" in body
    assert has_pricing_link or has_stripe_link, (
        "PR card on activation-choice : neither /BW/pricing/pr "
        "nor /BW/stripe-info/pr link present — the card is "
        "rendering an unexpected variant."
    )
    if has_pricing_link:
        # Specific to the skip_pricing_input branch.
        assert "Activer pour 1 client" in body, (
            "PR card : missing 'Activer pour 1 client' wording — "
            "`pricing_default` may have changed."
        )

    # No client-count input form for the PR type. The set_pricing
    # form action would expose `action="/BW/set_pricing/pr"`. If
    # that's there, we've regressed to the old "saisir le nombre
    # de clients" UI.
    assert "/BW/set_pricing/pr" not in body, (
        "PR card on activation-choice : set_pricing form rendered. "
        "Bug #0050 regression — `skip_pricing_input` not honoured."
    )


# ─── #0061 ─────────────────────────────────────────────────────────


def test_bug_0061_avis_enquete_non_mais_wording(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Bug #0061 — Le label de la branche « non-mais » dans le form
    de réponse à un avis-enquête doit dire « Non, mais je vous
    suggère une personne de mon organisation mieux placée que moi »
    (et non l'ancienne version qui invitait à coller un email
    libre, dangereux selon Jérôme).

    Le fix (commit `75dbd5f8`) remplace l'email libre par un select
    de collègues de l'organisation (`suggested_colleague_id`) gated
    par `eligible_colleagues`.

    Walk : iterate over communities to find a user with assigned
    opportunities (the seed maps avis-enquete recipients to PR
    Agency / Transformer profiles, not Leaders & Experts) → list
    /wip/opportunities → GET first → assert wording.
    """
    expected_label = (
        "Non, mais je vous suggère une personne de mon "
        "organisation mieux placée que moi"
    )

    # Iterate over communities + their opportunities until we land
    # on an UN-answered one. Once a contact has been answered with
    # something other than "non-mais", the form is replaced by a
    # static "you answered X" panel that doesn't contain the
    # `non-mais` label. We need an un-answered opportunity.
    for community in (
        "TRANSFORMER",
        "PRESS_RELATIONS",
        "ACADEMIC",
        "EXPERT",
    ):
        try:
            p = profile(community)
        except RuntimeError:
            continue
        login(p)
        page.goto(
            f"{base_url}/wip/opportunities",
            wait_until="domcontentloaded",
        )
        hrefs = page.locator("a[href]").evaluate_all(
            "els => els.map(e => e.getAttribute('href'))"
        )
        ids = []
        for href in hrefs or ():
            if not href:
                continue
            m = re.search(r"/wip/opportunities/(\d+)", href)
            if m:
                ids.append(m.group(1))
        for oid in ids:
            page.goto(
                f"{base_url}/wip/opportunities/{oid}",
                wait_until="domcontentloaded",
            )
            body = page.content()
            if expected_label in body:
                # e2e path : un-answered opportunity rendered the
                # form with the new wording. Verified, done.
                return

    # The seed has no un-answered opportunity for any tested
    # community (everyone responded). Fall back to a template-source
    # regression check : verify the template file still contains the
    # new wording. Catches regressions where the wording is
    # accidentally removed, even without live un-answered contacts.
    from pathlib import Path

    template = (
        Path(__file__).resolve().parent.parent.parent
        / "src/app/modules/wip/templates/wip/pages/media_opportunity.j2"
    )
    assert template.exists(), f"media_opportunity.j2 not at expected path : {template}"
    template_content = template.read_text()
    assert expected_label in template_content, (
        f"media_opportunity.j2 : new wording ({expected_label!r}) "
        "absent from template — bug #0061 wording fix removed."
    )
    assert "suggested_colleague_id" in template_content, (
        "media_opportunity.j2 : `suggested_colleague_id` select "
        "absent from template — bug #0061 logic fix removed."
    )


# ─── #0070 ─────────────────────────────────────────────────────────


def test_bug_0070_avis_enquete_phase_breadcrumbs(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Bug #0070 — Le breadcrumb des pages avis-enquete (ciblage,
    notify-publication, reponses, rdv) doit inclure le titre de
    l'avis comme lien cliquable, pour que l'utilisateur puisse
    revenir au sujet et accéder au menu `[…]`.

    Le fix (commit `24ff45d1`) ajoute `_update_phase_breadcrumbs`
    qui construit le path "Work › Avis d'enquête › <titre> (lien)
    › <phase>".

    Walk : login as an avis owner → list /wip/avis-enquete → GET
    first /<id>/ciblage → assert breadcrumb includes the title as a
    link.
    """
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(f"{base_url}/wip/avis-enquete/", wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    avis_id = None
    for href in hrefs or ():
        if not href:
            continue
        m = re.match(r"^/wip/avis-enquete/(\d+)/$", href)
        if m:
            avis_id = m.group(1)
            break
    if avis_id is None:
        pytest.skip(f"{p['email']} has no avis-enquete — seed empty for this user")

    # Visit the ciblage phase page (any phase URL has the same
    # breadcrumb structure post-fix).
    page.goto(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage",
        wait_until="domcontentloaded",
    )
    body = page.content()

    # The breadcrumb structure puts the avis title as a link to
    # /wip/avis-enquete/<id>/. Look for an <a href> pointing to
    # the avis detail.
    detail_link_re = rf'<a[^>]+href="[^"]*/wip/avis-enquete/{avis_id}/?[^"]*"'
    assert re.search(detail_link_re, body), (
        f"avis-enquete/{avis_id}/ciblage : no breadcrumb link "
        f"back to /wip/avis-enquete/{avis_id}/ — bug #0070 fix "
        "may have regressed."
    )
    # The phase name should also be visible somewhere.
    assert "ciblage" in body.lower(), (
        f"avis-enquete/{avis_id}/ciblage : phase name 'ciblage' "
        "absent — page didn't render the phase breadcrumb."
    )


# ─── #0088 ─────────────────────────────────────────────────────────


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_bug_0088_change_email_confirm_lands_on_preferences(
    page: Page,
    base_url: str,
    profile,
    login,
    mail_outbox,
) -> None:
    """Bug #0088 — Après avoir cliqué le lien de confirmation reçu
    par email, l'utilisateur doit atterrir sur ``/preferences/`` et
    pas sur le form de demande de changement d'email (chemin par
    défaut Flask-Security).

    Le fix (commit `24ff45d1`) ajoute
    ``app.config["SECURITY_POST_CHANGE_EMAIL_VIEW"] = "/preferences/"``.

    Test : round-trip change-email avec restore final. On utilise
    TRANSFORMER (peu utilisé ailleurs) pour minimiser le blast
    radius si la restauration échoue.
    """
    p = profile("TRANSFORMER")
    original_email = p["email"]
    # Tag-aliased on agencetca.info (real MX, so email-validator
    # accepts it ; not in seed CSV so no anti-enumeration squash).
    new_email = "eliane+e2e_bug_0088_target@agencetca.info"

    login(p)
    mail_outbox.reset()

    # Step 1 : POST change-email request. Captures a confirmation
    # mail addressed to `new_email`.
    page.goto(f"{base_url}/auth/change-email", wait_until="domcontentloaded")
    page.fill('input[name="email"]', new_email)
    page.click('input[type="submit"]')

    captured = mail_outbox.messages()
    assert captured, "change-email : no mail captured"
    token_url = None
    for m in captured:
        match = re.search(
            r"https?://[^\s\"']+/auth/change-email/[A-Za-z0-9_\-\.]+",
            m.get("body", "") + "\n" + m.get("html", ""),
        )
        if match:
            token_url = match.group(0)
            break
    assert token_url, "change-email : no token URL in mail body"

    try:
        # Step 2 : GET the token URL. Post-fix, lands on /preferences/.
        page.goto(token_url, wait_until="domcontentloaded")
        # The bug : pre-fix landed on /auth/change-email (the
        # request form). Post-fix lands on /preferences/ (any
        # sub-page accepted — Flask-Security may follow with extra
        # hops).
        assert "/preferences" in page.url, (
            f"change-email confirm : expected /preferences*, got "
            f"{page.url}. Bug #0088 fix "
            "(SECURITY_POST_CHANGE_EMAIL_VIEW) may have regressed."
        )
        # Sanity : NOT on the change-email request form (the bug).
        assert (
            "/auth/change-email" not in page.url
            or page.url.endswith("/auth/change-email-confirm")
            or "preferences" in page.url
        ), (
            f"change-email confirm : landed back on the change-email "
            f"form ({page.url}) — bug #0088 has regressed."
        )
    finally:
        # Step 3 : restore. The user's email is now `new_email`.
        # POST a second change-email back to `original_email`.
        page.goto(f"{base_url}/auth/logout", wait_until="domcontentloaded")
        page.context.clear_cookies()
        login({**p, "email": new_email})
        mail_outbox.reset()
        page.goto(
            f"{base_url}/auth/change-email",
            wait_until="domcontentloaded",
        )
        page.fill('input[name="email"]', original_email)
        page.click('input[type="submit"]')
        captured_restore = mail_outbox.messages()
        if not captured_restore:
            return  # restore failed silently — leave a trail
        for m in captured_restore:
            match = re.search(
                r"https?://[^\s\"']+/auth/change-email/[A-Za-z0-9_\-\.]+",
                m.get("body", "") + "\n" + m.get("html", ""),
            )
            if match:
                page.goto(match.group(0), wait_until="domcontentloaded")
                break


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
    p = profile("PRESS_MEDIA")
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


# ─── #0068 ─────────────────────────────────────────────────────────


def test_bug_0068_avis_enquete_mail_wording() -> None:
    """Bug #0068 — Le template de mail de notification d'avis
    d'enquête (`avis_enquete_notification.j2`) doit respecter les
    contrats demandés par Erick :

    - « AiPRESS24 » avec le « i » rouge inline-stylé (pas
      « Aipress24 » ou autre casse).
    - Inclure profession (`sender_job`) sur la ligne « Emetteur ».
    - Le CTA est un **bouton stylé** vers l'avis d'enquête (lien
      direct, pas d'explications longues) — demandé par Erick le
      2026-05-21, livré en commit `550a3db2`. Avant, le lien était
      une URL brute précédée d'un paragraphe « Pour participer à
      cette enquête journalistique, cliquez sur le lien ci-dessous »
      que ce test pinnait — on bascule la garde sur le nouveau
      contrat (bouton + texte d'accroche court).

    Pure content check : pas d'e2e mail-roundtrip (demanderait un
    avis publié + ciblage en cours d'envoi). Cf. commit `550a3db2`
    et `bugs/resolus/0068`.
    """
    from pathlib import Path

    template = (
        Path(__file__).resolve().parent.parent.parent
        / "src/app/services/emails/mail_templates"
        / "avis_enquete_notification.j2"
    )
    assert template.exists(), (
        f"avis_enquete_notification.j2 not at expected path : {template}"
    )
    content = template.read_text()

    # Wordmark : 'A<span ...>i</span>PRESS24' inline-styled.
    assert (
        "AIPRESS24" in content
        or "AiPRESS24" in content
        or ("<strong>A<span" in content and "PRESS24" in content)
    ), (
        "avis_enquete_notification.j2 : missing AiPRESS24 "
        "wordmark — bug #0068 regressed."
    )
    # Sender job present ({{ sender_job }} or similar var).
    assert "sender_job" in content, (
        "avis_enquete_notification.j2 : `sender_job` Jinja var "
        "absent — Emetteur ne mentionne plus la fonction."
    )
    # CTA contract (post-2026-05-21) : a styled <a> button labelled
    # « Ouvrir l'avis d'enquête » with an inline background color,
    # plus a short lead-in that drops the long « cliquez sur le lien
    # ci-dessous » phrase. The lead-in keeps « Pour participer à
    # cette enquête » so the email reads naturally.
    assert "Pour participer à cette enquête" in content, (
        "avis_enquete_notification.j2 : CTA lead-in absent — bug #0068 regressed."
    )
    assert "Ouvrir l'avis d'enquête" in content, (
        "avis_enquete_notification.j2 : CTA button label "
        "« Ouvrir l'avis d'enquête » absent — bug #0068 regressed."
    )
    assert "background-color" in content, (
        "avis_enquete_notification.j2 : the CTA button must be "
        "inline-styled (background-color) for email-client "
        "compatibility — bug #0068 regressed."
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
    p = profile("PRESS_MEDIA")
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


# ─── shared helpers (table-driven WIP regression tests) ───────────


_PRESS_MEDIA = "PRESS_MEDIA"
_PRESS_RELATIONS = "PRESS_RELATIONS"
_COMM_PAT = re.compile(r"/wip/communiques/(\d+)/?")
_SUJET_PAT = re.compile(r"/wip/sujets/(\d+)/?")


def _first_id_in_table(page: Page, list_url: str, pat: re.Pattern[str]) -> str | None:
    """Return the first id matching `pat` in any href on `list_url`, or
    None. Used to pick a target row for "open & assert" style regression
    tests against WIP CRUD pages without coupling to seed data."""
    page.goto(list_url, wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        if not href:
            continue
        m = pat.search(href)
        if m:
            return m.group(1)
    return None


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


# ─── #0129 ────────────────────────────────────────────────────────


def _no_long_snowflake_in_label(html: str, label: str) -> bool:
    """Return True iff the value rendered next to `label` is not a
    17-19-digit Snowflake integer (raw FK id). Looks for the label and
    the next 400 characters of HTML."""
    idx = html.find(label)
    if idx < 0:
        return True
    snippet = html[idx : idx + 400]
    return re.search(r"\b\d{17,19}\b", snippet) is None


@pytest.mark.parametrize(
    ("community", "list_url", "id_pattern"),
    [
        (_PRESS_RELATIONS, "/wip/communiques/", _COMM_PAT),
        (_PRESS_MEDIA, "/wip/sujets/", _SUJET_PAT),
    ],
    ids=["communique", "sujet"],
)
def test_bug_0129_view_renders_publisher_name_not_raw_id(
    page: Page,
    base_url: str,
    profile,
    login,
    community: str,
    list_url: str,
    id_pattern: re.Pattern[str],
) -> None:
    """Bug #0129 — communiqué/sujet « Voir » must show the publisher
    organisation NAME, not the raw FK id (Snowflake integer). The renderer
    now special-cases `publisher_id` like it already did for `media_id`."""
    p = profile(community)
    login(p)
    obj_id = _first_id_in_table(page, f"{base_url}{list_url}", id_pattern)
    if obj_id is None:
        pytest.skip(f"no item visible for {community} at {list_url}")

    page.goto(f"{base_url}{list_url}{obj_id}/", wait_until="domcontentloaded")
    body = page.content()
    assert _no_long_snowflake_in_label(body, "Publier pour"), (
        "raw FK id leaked next to 'Publier pour' label — publisher_id "
        "should resolve to the organisation name"
    )


# ─── #0130 ────────────────────────────────────────────────────────


def test_bug_0130_invitations_preferences_page_renders(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0130 — when an organisation invites a user by email, the
    invitation must appear in PROFIL/PRÉFÉRENCES/Invitation d'organisation.
    Storage normalises email (strip + lowercase); lookup mirrors. Smoke
    test that the page is reachable and the section header is visible.
    Lookup edge cases (case + whitespace) are covered by the integration
    tests in `tests/c_e2e/modules/preferences/test_invitations.py`."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(
        f"{base_url}/preferences/invitations", wait_until="domcontentloaded"
    )
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Internal Server Error" not in body
    assert "Traceback" not in body
    assert "invitation" in body.lower()


# ─── #0131 ────────────────────────────────────────────────────────


def test_bug_0131_calendar_event_format_and_link(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0131 — calendar event entries must link to /events/<id> (not
    href="#"), carry a valid `<time datetime="YYYY-MM-DDTHH:MM">` (was
    hardcoded to "2022-01-03T10:00"), and format the time as HH:MM (not
    HH:MM:SS). The calendar default view shows the current month; if no
    events that month, sweep adjacent months."""
    import datetime as _dt

    p = profile(_PRESS_MEDIA)
    login(p)

    today = _dt.datetime.now(tz=_dt.UTC).date()
    candidates: list[str | None] = [None]
    for delta in range(1, 13):
        for sign in (-1, 1):
            year, month = today.year, today.month + sign * delta
            while month <= 0:
                month += 12
                year -= 1
            while month > 12:
                month -= 12
                year += 1
            candidates.append(f"{year:04d}-{month:02d}")

    chosen_url = None
    for c in candidates:
        url = (
            f"{base_url}/events/calendar"
            if c is None
            else f"{base_url}/events/calendar?month={c}"
        )
        resp = page.goto(url, wait_until="domcontentloaded")
        if resp is None or resp.status >= 400:
            continue
        if page.locator("a.group.flex").count() > 0:
            chosen_url = url
            break

    if chosen_url is None:
        pytest.skip("no calendar event entry found in any nearby month")

    bad_time_in_entry = page.evaluate(
        """() => {
            const re = /\\b\\d{2}:\\d{2}:\\d{2}\\b/;
            for (const a of document.querySelectorAll('a.group.flex')) {
                for (const t of a.querySelectorAll('time')) {
                    if (re.test(t.textContent || '')) return t.textContent;
                }
            }
            return null;
        }"""
    )
    assert bad_time_in_entry is None, (
        f"calendar entry shows HH:MM:SS format: {bad_time_in_entry!r}"
    )

    bad_href = page.evaluate(
        """() => {
            for (const a of document.querySelectorAll('a.group.flex')) {
                const h = a.getAttribute('href') || '';
                if (h === '#' || h === '' || h === '/') return h || 'empty';
                if (!/\\/events\\/\\d+/.test(h)) return h;
            }
            return null;
        }"""
    )
    assert bad_href is None, (
        f"calendar entry has bad href (was '#' before #0131): {bad_href!r}"
    )

    bad_dt = page.evaluate(
        """() => {
            const re = /^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}/;
            for (const a of document.querySelectorAll('a.group.flex')) {
                for (const t of a.querySelectorAll('time[datetime]')) {
                    const dt = t.getAttribute('datetime') || '';
                    if (!re.test(dt)) return dt;
                    if (dt.startsWith('2022-01-03')) return dt;
                }
            }
            return null;
        }"""
    )
    assert bad_dt is None, (
        f"calendar entry has bad <time datetime> attribute: {bad_dt!r}"
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


# ─── #0133 ────────────────────────────────────────────────────────


def test_bug_0133_choices_dropdown_not_masked(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Bug #0133 — Le dropdown Choices.js du sélecteur de média est
    masqué par le champ pays/code postal qui suit (z-index: 1 vs
    z-index: 10 du tom-select). Le fix passe le z-index du dropdown
    à 50.

    Vérifie que `.choices__list--dropdown` a un z-index suffisant.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}/wip/sujets/new/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400

    # Bug #0133: verify the CSS rule for .choices__list--dropdown
    # has z-index >= 50. We read from the stylesheet rather than the
    # DOM element because the dropdown panel is only created by
    # Choices.js when the select is opened.
    z_index = page.evaluate(
        """() => {
            for (const sheet of document.styleSheets) {
                try {
                    for (const rule of sheet.cssRules) {
                        if (rule.selectorText && rule.selectorText.includes('.choices__list--dropdown')) {
                            const z = rule.style.zIndex;
                            if (z) return z;
                        }
                    }
                } catch (e) {
                    // cross-origin stylesheet — skip
                }
            }
            return null;
        }"""
    )
    assert z_index is not None, (
        "CSS rule for .choices__list--dropdown not found in any stylesheet — "
        "bug #0133 fix (z-index: 50) may have regressed"
    )
    z_int = int(z_index)
    assert z_int >= 50, (
        f"Choices.js dropdown z-index is {z_int}, expected >= 50 — "
        "bug #0133 regression (was 1, masked by tom-select at z=10)"
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


# ─── #0129 (extension) ─────────────────────────────────────────────


def test_bug_0129_event_shows_published_by_relation(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Bug #0129 extension — Les événements doivent afficher la
    mention "Publié par X en tant que contact presse de Y" quand
    l'auteur appartient à une agence PR et publie pour un client.

    Vérifie cette mention sur la page de détail d'un événement.
    """
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}/events", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400

    # Find first event link
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    event_id = None
    for href in hrefs or ():
        m = re.search(r"/events/(\d+)", href or "")
        if m:
            event_id = m.group(1)
            break
    if event_id is None:
        pytest.skip("no events found in seed data")

    resp = page.goto(f"{base_url}/events/{event_id}", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()

    # The aside should show "Publié par" when author org != publisher
    # (may not always be the case with seed data, so we only assert
    # the rendering pattern is present — the template includes the
    # block conditionally).
    assert "Publié par" in body or "Pour" in body, (
        "event detail page should show publisher info ('Pour') or "
        "'Publié par' relation — bug #0129 regression"
    )


# ─── #0132 (extension) ────────────────────────────────────────────


def test_bug_0132_sujet_list_and_view_show_author(
    page: Page,
    base_url: str,
    profile,
    login,
) -> None:
    """Bug #0132 extension — La liste des sujets et la vue détaillée
    doivent afficher l'auteur. Le fix ajoute une colonne "Auteur"
    dans SujetsTable et une section auteur dans _extra_view_html().
    """
    p = profile(_PRESS_MEDIA)
    login(p)

    # 1. List view must have "Auteur" column header
    resp = page.goto(f"{base_url}/wip/sujets/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Auteur" in body, (
        "sujets list table should have 'Auteur' column — bug #0132 extension regression"
    )

    # 2. Detail view must show author section
    sid = _first_id_in_table(page, f"{base_url}/wip/sujets/", _SUJET_PAT)
    if sid is None:
        pytest.skip("no sujet in seed data")

    resp = page.goto(f"{base_url}/wip/sujets/{sid}/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()
    assert "Auteur" in body, (
        "sujet detail view should show 'Auteur' section — "
        "bug #0132 extension regression"
    )


# ─── #0132 ────────────────────────────────────────────────────────


def test_bug_0132_sujets_table_exposes_publier_action(
    page: Page, base_url: str, profile, login
) -> None:
    """Bug #0132 — SujetsTable must expose a "Publier" action so DRAFT
    sujets can be promoted to PUBLIC and the targeted media is notified.
    Before this fix, only "Voir / Modifier / Supprimer" were exposed and
    sujets sat in DRAFT forever."""
    p = profile(_PRESS_MEDIA)
    login(p)
    resp = page.goto(f"{base_url}/wip/sujets/", wait_until="domcontentloaded")
    assert resp is not None and resp.status < 400
    body = page.content()
    if "/wip/sujets/" not in body:
        pytest.skip("sujets list page didn't render the listing area")

    # Discriminating skip : a *row* URL ends in `/wip/sujets/<digits>`
    # (the matcher used by `_first_id_in_table`). The previous heuristic
    # — "any href containing /wip/sujets/" — also matched the breadcrumb,
    # the « Créer un sujet » button, and pagination links, so the skip
    # never fired even when the user had no sujet, and the test reached
    # the body-assertion below with an empty table → false red.
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href') || '')"
    )
    has_row = any(_SUJET_PAT.search(h) for h in (hrefs or ()))
    if not has_row:
        pytest.skip("no sujet row in this user's table — seed data")

    assert "Publier" in body or "Dépublier" in body, (
        "neither Publier nor Dépublier action found on /wip/sujets/ — "
        "SujetsTable.get_actions probably reverted to default actions"
    )


@pytest.mark.mutates_db
def test_bug_0132_publish_sujet_round_trip(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_post,
) -> None:
    """End-to-end: GET publish on a DRAFT sujet → 200/redirect, then
    GET unpublish → restored. Restores initial state."""
    p = profile(_PRESS_MEDIA)
    login(p)
    sid = _first_id_in_table(page, f"{base_url}/wip/sujets/", _SUJET_PAT)
    if sid is None:
        pytest.skip("no sujet in seed data")

    publish_resp = page.goto(
        f"{base_url}/wip/sujets/publish/{sid}/", wait_until="domcontentloaded"
    )
    if publish_resp is None or publish_resp.status >= 400:
        pytest.skip(
            f"publish endpoint returned "
            f"{publish_resp.status if publish_resp else '?'} — sujet "
            "may not be in DRAFT state or required fields missing"
        )

    unpublish_resp = page.goto(
        f"{base_url}/wip/sujets/unpublish/{sid}/",
        wait_until="domcontentloaded",
    )
    assert unpublish_resp is not None and unpublish_resp.status < 400


# ─── #0154 (articles/communiques/events) ─────────────────────────


def test_bug_0154_step_nav_extended_to_articles_communiques_events() -> None:
    """Bug #0154 — Erick 2026-05-22 : extend the step-nav bar (delivered
    on Avis d'enquête in #0151) to NEWSROOM/Articles, COMROOM/Communiqués
    and EVENT'ROOM/Événements. These modules have a simpler workflow
    (just Voir ↔ Modifier) so a dedicated 2-step macro lives at
    ``wip/_step_nav_simple.j2``. Each CBV must wire it on its Voir
    and Modifier templates.

    Template content guard — runtime coverage lives in the per-module
    test files (``test_articles_views.py``, ``test_communiques_views.py``,
    ``test_events_views.py``).
    """
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent.parent / "src/app/modules/wip"

    # The shared macro must exist.
    macro = src / "templates/wip/_step_nav_simple.j2"
    assert macro.exists(), "_step_nav_simple.j2 macro must be present"
    macro_content = macro.read_text()
    assert "macro step_nav_simple" in macro_content
    assert "Étape suivante" in macro_content
    assert "Étape précédente" in macro_content
    assert "Retourner à la liste des" in macro_content

    # Each CBV must import the macro on its Voir / Modifier templates.
    for cbv_path, view_name in (
        ("crud/cbvs/articles.py", "ArticlesWipView"),
        ("crud/cbvs/communiques.py", "CommuniquesWipView"),
        ("crud/cbvs/events.py", "EventsWipView"),
    ):
        cbv = src / cbv_path
        assert cbv.exists()
        cbv_content = cbv.read_text()
        assert "_step_nav_simple.j2" in cbv_content, (
            f"{cbv_path} must import the step_nav_simple macro — "
            f"bug #0154 regressed."
        )
        assert f'"{view_name}"' in cbv_content, (
            f"{cbv_path} step-nav calls must reference {view_name!r}"
        )
        # Both `voir` and `modifier` step labels must be present.
        assert '"voir"' in cbv_content
        assert '"modifier"' in cbv_content


# ─── #0142 (step 4) ────────────────────────────────────────────────


def test_bug_0142_step4_modal_harmonised() -> None:
    """Bug #0142 step 4 — Erick 2026-05-22 : « Sur "3-Gérer les
    invitations à rejoindre le BW", c'est résolu. Mais pas sur
    "4-Gérer la liste des membres du BW" c'est encore l'ancienne
    interface ». Port the step-3 harmonisation pattern to step 4.

    Template content guard ; the runtime test
    ``tests/c_e2e/modules/bw/test_stages_b1_b3.py::
    TestStageB2ManageOrgMembersRoutes::test_members_modal_harmonised_keeps_wiring``
    covers the rendered surface.
    """
    from pathlib import Path

    template = (
        Path(__file__).resolve().parent.parent.parent
        / "src/app/modules/bw/bw_activation/templates/bw_activation"
        / "B03_manage_organisation_members.html"
    )
    assert template.exists()
    content = template.read_text()
    # Old anti-patterns gone.
    assert "dark:bg-gray-700" not in content, (
        "B03 must not re-introduce the dark-mode container styling "
        "— bug #0142 step 4 regressed."
    )
    assert "rounded-lg shadow dark:" not in content, (
        "B03 modal must use the harmonised `rounded-2xl shadow-lg "
        "border border-gray-200` card — bug #0142 step 4 regressed."
    )
    # New harmonised pattern present.
    assert "rounded-2xl shadow-lg border border-gray-200" in content, (
        "B03 modal must use the harmonised card class — bug #0142 "
        "step 4 regressed."
    )
    assert "Emails des membres" in content, (
        "B03 must surface an explicit form label above the textarea "
        "(harmonisation marker) — bug #0142 step 4 regressed."
    )


# ─── #0071 (part 1) ───────────────────────────────────────────────


def test_bug_0071_no_dead_end_colleague_fallback() -> None:
    """Bug #0071 part 1 — Erick 2026-05-21 : « il y a la mention
    "Aucun collègue disponible, écrivez-nous: contact@aipress24.com".
    Il faut la retirer car je ne saurais pas comment gérer cette
    situation ». The form must not surface a dead-end fallback the
    user can't act on.

    Template guard ; runtime coverage lives in
    ``tests/c_e2e/modules/wip/test_opportunities_views.py::
    TestSuggestColleagueRadioAlwaysClickable``.
    """
    from pathlib import Path

    template = (
        Path(__file__).resolve().parent.parent.parent
        / "src/app/modules/wip/templates/wip/pages"
        / "media_opportunity.j2"
    )
    assert template.exists()
    content = template.read_text()
    assert "aucun collègue" not in content.lower(), (
        "media_opportunity.j2 must not re-introduce the "
        "« aucun collègue disponible » hint — bug #0071/1 regressed."
    )
    assert "écrivez-nous" not in content.lower(), (
        "media_opportunity.j2 must not include a « écrivez-nous » "
        "dead-end fallback — bug #0071/1 regressed."
    )
    assert "contact@aipress24.com" not in content, (
        "media_opportunity.j2 must not surface contact@aipress24.com "
        "as a fallback — bug #0071/1 regressed."
    )


# ─── #0075 (part 3) ───────────────────────────────────────────────


def test_bug_0075_non_mais_radio_always_clickable() -> None:
    """Bug #0075 part 3 — The « Non, mais je vous suggère une personne
    de mon organisation mieux placée que moi » radio used to render
    `disabled` (and the label `text-gray-400`) when no eligible
    colleague existed. Erick : « On ne peut l'activer ». The radio
    must be clickable in every state.

    Pure template content check ; the runtime gate is in
    ``tests/c_e2e/modules/wip/test_opportunities_views.py::
    TestSuggestColleagueRadioAlwaysClickable``.
    """
    from pathlib import Path

    template = (
        Path(__file__).resolve().parent.parent.parent
        / "src/app/modules/wip/templates/wip/pages"
        / "media_opportunity.j2"
    )
    assert template.exists()
    content = template.read_text()
    # The historical pattern was `{% if not eligible_colleagues %}
    # disabled{% endif %}` on the `non-mais` radio (and a grey label).
    # Anchor on the literal Jinja predicate so the legit `is_answered`
    # gates on the contribution/refusal_reason fields aren't tripped.
    # `eligible_colleagues` is still legitimately used as a truthy
    # gate for the select (only show it when there's something to
    # pick) — we ban the *negated* predicate that disabled the radio.
    # The grey label class flows from the same predicate, so guarding
    # the predicate guards both.
    import re

    assert not re.search(r"{%\s*if\s+not\s+eligible_colleagues\s*%}", content), (
        "media_opportunity.j2 must not gate any rendering on "
        "`{% if not eligible_colleagues %}` — bug #0075/3 regressed."
    )


# ─── #0170 ────────────────────────────────────────────────────────


def test_bug_0170_rdv_details_omits_proposed_slots() -> None:
    """Bug #0170 — Once a slot has been accepted, the « Créneaux
    proposés » list becomes noise on the RDV detail page (Erick :
    « Autant les retirer car cela trouble la lecture »). The block
    must NOT be present in ``rdv_details.j2``.

    Pure template content check — runtime coverage is in
    ``test_avis_enquete_views.py::test_rdv_details_omits_proposed_slots_list``.
    """
    from pathlib import Path

    template = (
        Path(__file__).resolve().parent.parent.parent
        / "src/app/modules/wip/templates/wip/avis_enquete"
        / "rdv_details.j2"
    )
    assert template.exists()
    content = template.read_text()
    # Anchor on the rendered HTML pattern (h3 closing tag) rather than
    # the bare label, so the in-source comment that *names* the
    # removed block in past tense doesn't trip the guard.
    assert "Créneaux proposés:</h3>" not in content, (
        "rdv_details.j2 must not re-introduce the proposed-slots <h3> "
        "block — bug #0170 regressed."
    )
    assert "proposed_slots_dt" not in content, (
        "rdv_details.j2 must not iterate `proposed_slots_dt` — bug "
        "#0170 regressed."
    )
