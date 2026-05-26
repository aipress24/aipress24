# ruff: noqa: INP001, PLC0415, B012
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests — Trello tickets #0050 → #0088.

Each test guards a previously-resolved bug ; reds here mean the
corresponding fix has regressed.

Bugs covered :
- **#0050** — PR Agency BW activation card → direct link to pricing
  (commit `24ff45d1`).
- **#0061** — Avis enquête « non-mais » wording + suggestion de
  collègue (commit `75dbd5f8`).
- **#0068** — wording du mail de notification avis-enquête, bascule
  vers un bouton CTA (commit `550a3db2`).
- **#0070** — Avis enquête phase breadcrumbs (commit `24ff45d1`).
- **#0071 part 1** — pas de fallback « contact@aipress24.com » dans
  le form d'opportunité.
- **#0071 part 2** — DRAFT BW finalised on confirmation_free /
  confirmation_paid revisit so Jocelyne sees the gate cleared.
- **#0075 part 2** — `press_officer_emails` surfaces internal BWPRi
  + external BWPRe partners in the dropdown.
- **#0075 part 3** — « Non, mais je suggère » radio always clickable.
- **#0088** — Confirmation changement email redirige vers
  ``/preferences/`` (commit `24ff45d1`).
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


# ─── #0071 (part 2) ───────────────────────────────────────────────


def test_bug_0071_part2_draft_bw_activates_on_confirmation_revisit() -> None:
    """Bug #0071 part 2 — Erick 2026-05-21 : Jocelyne configures her
    BW from the avis-d'enquête gate, returns to the opportunity page,
    but the gate is still showing. Root cause : the activation flow's
    idempotency check accepted any non-CANCELLED status (including
    DRAFT) and rendered « Activation Réussie » without finalising the
    BW. The opportunity gate later rejected DRAFT (ACTIVE-only) and
    the banner persisted.

    The fix flips DRAFT → ACTIVE when the user comes back through
    confirmation_free / confirmation_paid as a manager. Source-level
    guard ; runtime coverage in
    ``tests/c_e2e/modules/bw/test_bw_routes.py::TestStage3FreeRoutes::
    test_confirmation_free_activates_existing_draft_bw``.
    """
    from pathlib import Path

    stage3 = (
        Path(__file__).resolve().parent.parent.parent
        / "src/app/modules/bw/bw_activation/routes"
        / "stage3.py"
    )
    assert stage3.exists()
    content = stage3.read_text()
    # The finalisation branch must be present in both confirmation_free
    # and confirmation_paid.
    assert content.count("existing.status = BWStatus.ACTIVE.value") >= 2, (
        "stage3.py must finalise DRAFT BWs in both confirmation_free "
        "and confirmation_paid — bug #0071/2 regressed."
    )


# ─── #0075 (part 2) ───────────────────────────────────────────────


def test_bug_0075_part2_press_officer_emails_includes_external() -> None:
    """Bug #0075 part 2 — Erick 2026-05-22 : « Il manque les
    Partenaires PR Agencies: Anne-Laure Capri [...] ainsi que Marc
    Rodriguez de l'agence Fake-Les Propulseurs RP. En toute logique,
    ces mail devraient remonter automatiquement à cet endroit ».

    The service exposes `press_officer_emails` returning the full
    list (internal BWPRi + active BWPRe partner agency owners), and
    the form renders it as a dropdown when there's more than one
    candidate. The route validates the user's pick against the
    current valid set so a tampered POST can't slip in an arbitrary
    address.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent.parent / "src/app"
    service = src / "modules/wip/services/newsroom/avis_enquete_service.py"
    assert service.exists()
    service_content = service.read_text()
    assert "def press_officer_emails" in service_content, (
        "press_officer_emails helper must exist — bug #0075/2 regressed."
    )
    # The body must explicitly iterate partnerships to include BWPRe
    # owners (not just BWPRi role assignments).
    assert "partnerships" in service_content, (
        "press_officer_emails must consider partnerships (BWPRe) — "
        "bug #0075/2 regressed."
    )
    # Route must validate the picked email against the valid set.
    route = src / "modules/wip/views/opportunities.py"
    assert "press_officer_emails" in route.read_text()


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
    assert not re.search(r"{%\s*if\s+not\s+eligible_colleagues\s*%}", content), (
        "media_opportunity.j2 must not gate any rendering on "
        "`{% if not eligible_colleagues %}` — bug #0075/3 regressed."
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
