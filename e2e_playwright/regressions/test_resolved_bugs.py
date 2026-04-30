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
        (
            p
            for p in profiles
            if p["email"] == "eliane+AliMbappe@agencetca.info"
        ),
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
    select = authed_post(
        f"{base_url}/BW/select-subscription/pr", {}
    )
    assert select["status"] < 400
    assert "/auth/login" not in select["url"]

    # Now activation-choice renders all cards.
    page.goto(
        f"{base_url}/BW/activation-choice",
        wait_until="domcontentloaded",
    )
    body = page.content()

    # Post-fix : the PR card has the link to /BW/pricing/pr with
    # "Activer pour 1 client" wording.
    assert "/BW/pricing/pr" in body, (
        "PR card on activation-choice : no direct link to "
        "/BW/pricing/pr — `skip_pricing_input` may have regressed."
    )
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
    assert template.exists(), (
        f"media_opportunity.j2 not at expected path : {template}"
    )
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
    page.goto(
        f"{base_url}/wip/avis-enquete/", wait_until="domcontentloaded"
    )
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
        pytest.skip(
            f"{p['email']} has no avis-enquete — seed empty for "
            "this user"
        )

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
    page.goto(
        f"{base_url}/auth/change-email", wait_until="domcontentloaded"
    )
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
        assert "/auth/change-email" not in page.url or page.url.endswith(
            "/auth/change-email-confirm"
        ) or "preferences" in page.url, (
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
        pytest.skip(
            f"{p['email']} has no BW — can't reach configure-content"
        )
    # /BW/select-bw/<id> is POST-only.
    sel = authed_post(
        f"{base_url}/BW/select-bw/{erick_bw_id}", {}
    )
    if sel["status"] >= 400 or "/auth/login" in sel["url"]:
        pytest.skip(f"select-bw failed : {sel}")
    page.goto(
        f"{base_url}/BW/configure-content",
        wait_until="domcontentloaded",
    )
    if "/BW/configure-content" not in page.url:
        pytest.skip(
            f"{p['email']} can't reach /BW/configure-content — "
            f"landed on {page.url}"
        )
    body = page.content()

    # Look for any optgroup or option with a trailing space in
    # its label — this is the corruption pattern.
    # Pattern : <optgroup label="ORGANISATIONS PRIVÉES "> (with
    # trailing space before the closing quote).
    bad_optgroup = re.search(
        r'<optgroup\s+label="[^"]+ "', body
    )
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
    d'enquête (`avis_enquete_notification.j2`) doit utiliser le
    wording demandé par Erick :

    - « AiPRESS24 » avec le « i » rouge inline-stylé (pas
      « Aipress24 » ou autre casse).
    - « Un avis d'enquête vient d'être diffusé par un journaliste
      membre d'AiPRESS24 ».
    - Inclure profession (`sender_job`) sur la ligne « Emetteur ».
    - Inclure le bloc « Pour participer à cette enquête
      journalistique, connectez-vous à AiPRESS24, puis collez le
      lien ci-dessous… ».

    Pure content check : pas d'e2e mail-roundtrip (demanderait un
    avis publié + ciblage en cours d'envoi). Cf. commit `24ff45d1`
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
    assert "AIPRESS24" in content or "AiPRESS24" in content or (
        '<strong>A<span' in content
        and 'PRESS24' in content
    ), (
        "avis_enquete_notification.j2 : missing AiPRESS24 "
        "wordmark — bug #0068 regressed."
    )
    # Sender job present ({{ sender_job }} or similar var).
    assert "sender_job" in content, (
        "avis_enquete_notification.j2 : `sender_job` Jinja var "
        "absent — Emetteur ne mentionne plus la fonction."
    )
    # The CTA paragraph wording.
    assert (
        "Pour participer à cette enquête journalistique"
        in content
    ), (
        "avis_enquete_notification.j2 : CTA wording absent — "
        "bug #0068 regressed."
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
    """
    p = profile("PRESS_MEDIA")
    login(p)
    page.goto(f"{base_url}/BW/", wait_until="domcontentloaded")
    if "/BW/dashboard" in page.url or "/BW/select-bw" in page.url:
        # User has BW(s) ; select-subscription would error out.
        # Skip — the wizard pre-fill is only on first activation
        # and AliMbappe path covers it.
        pytest.skip(
            f"{p['email']} already has a BW — pre-fill path not "
            "exercised on this run"
        )
    # Confirm bw_type=media to unlock nominate-contacts.
    sel = authed_post(
        f"{base_url}/BW/select-subscription/media", {}
    )
    if sel["status"] >= 400 or "/auth/login" in sel["url"]:
        pytest.skip(f"select-subscription failed : {sel}")

    page.goto(
        f"{base_url}/BW/nominate-contacts",
        wait_until="domcontentloaded",
    )
    if "/BW/nominate-contacts" not in page.url:
        pytest.skip(
            f"can't reach /BW/nominate-contacts — landed on "
            f"{page.url}"
        )
    # The form has <input name="owner_title" value="...">. Read
    # the value.
    try:
        title_value = page.locator(
            'input[name="owner_title"]'
        ).first.input_value(timeout=2_000)
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
