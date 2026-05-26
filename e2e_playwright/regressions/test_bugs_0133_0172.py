# ruff: noqa: INP001, PLC0415, PT018
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Regression tests — Trello tickets #0133 → #0172.

Bugs covered :
- **#0133** — Choices.js dropdown z-index ≥ 50 (was masked by
  tom-select / postal-code field).
- **#0142 (step 4)** — BW « Gérer la liste des membres » modal
  harmonised with step-3 pattern.
- **#0154** — step-nav extended from Avis d'enquête to NEWSROOM/
  Articles, COMROOM/Communiqués, EVENT'ROOM/Événements.
- **#0166** — `get_manageable_business_walls_for_user` unions in
  client BWs reachable through active partnerships (PR Agency owner
  must see client BWs in /BW/select-bw).
- **#0169 parts 1 & 2** — partner agency owner gets cloche + mail
  on partnership revoke.
- **#0169 part 3** — revoked partnerships surfaced in
  /preferences/invitations with a « Confirmer » button.
- **#0170** — RDV details page omits the « Créneaux proposés » list
  (Erick : « Autant les retirer car cela trouble la lecture »).
- **#0172** — `Event.publish()` requires both start/end dates
  (Sophie-Anne : events published without dates were silently
  filtered out of /events/).
"""

from __future__ import annotations

from _shared import _PRESS_MEDIA
from playwright.sync_api import Page

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


# ─── #0166 ────────────────────────────────────────────────────────


def test_bug_0166_manageable_bws_include_partnership_client() -> None:
    """Bug #0166 — Alfred Delarue (PR Agency owner) : « lorsque je
    clique sur le bouton "Gérer mes Business Walls", je tombe sur mon
    propre BW. Il n'y a pas d'interface pour gérer les BW de mes
    clients ».

    Root cause : `get_manageable_business_walls_for_user` only
    included BWs the user *owned* or held a DASHBOARD_ACCESS_ROLES
    role on (BW_OWNER / BWMi / BWMe). A PR Agency owner's access to
    client BWs flows through a Partnership, not a direct role on the
    client BW, so client BWs never appeared in /BW/select-bw and the
    user could never switch into a client's management surface.

    Fix : the helper also unions in client BWs reachable through an
    active Partnership whose `partner_bw_id` belongs to one of the
    user's agency BWs. Source-level guard ; runtime coverage in
    ``tests/b_integration/modules/bw/test_user_utils.py::
    TestGetManageableBusinessWallsForUser``.
    """
    from pathlib import Path

    src = (
        Path(__file__).resolve().parent.parent.parent
        / "src/app/modules/bw/bw_activation/user_utils.py"
    )
    content = src.read_text()
    assert "Partnership.partner_bw_id.in_(agency_bw_id_strs)" in content, (
        "get_manageable_business_walls_for_user must union in client "
        "BWs from active partnerships — bug #0166 regressed."
    )
    assert "_ACTIVE_PARTNERSHIP_STATUSES" in content


# ─── #0169 (parts 1 & 2) ──────────────────────────────────────────


def test_bug_0169_revoke_partnership_notifies_partner() -> None:
    """Bug #0169 — Erick 2026-05-22 : when a client revokes a
    partnership, the PR Agency owner had no signal (no cloche, no
    mail, the row just disappeared). Add (a) an in-app notification
    and (b) an email naming the client org so the agency owner knows
    they lost a client.

    Source-level guard ; runtime coverage in
    ``tests/b_integration/modules/bw/test_bw_invitation_integration.py::
    TestRevokePartnershipIntegration::test_revoke_notifies_partner_agency_owner``.

    Part 3 (explicit revoked-partnership row in
    /preferences/invitations with a « Confirmer » button) is a
    separate follow-up — the cloche + email cover the main
    awareness gap.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent.parent / "src/app"
    invitation_module = src / "modules/bw/bw_activation/bw_invitation.py"
    assert invitation_module.exists()
    content = invitation_module.read_text()
    assert "notify_partnership_revoked" in content, (
        "revoke_partnership must trigger an in-app notification — "
        "bug #0169 regressed."
    )
    assert "send_partnership_revoked_mail" in content, (
        "revoke_partnership must trigger an email — bug #0169 regressed."
    )
    # The mailer must exist.
    mailer = src / "services/emails/mailers.py"
    assert "BWPartnershipRevokedMail" in mailer.read_text()
    # The template must exist.
    tpl = src / "services/emails/mail_templates/bw_partnership_revoked.j2"
    assert tpl.exists(), "bw_partnership_revoked.j2 must be present"


# ─── #0169 (part 3) ────────────────────────────────────────────────


def test_bug_0169_part3_revoked_partnership_row_in_preferences() -> None:
    """Bug #0169 part 3 — Erick : « Indiquer dans PROFIL/PRÉFÉRENCES/
    Invitations d'organisations [...] la fin du partenariat [...] avec
    un bouton "Confirmer" qui conduira à éliminer cette ligne ».

    Source-level guards : the InvitationsView must expose a
    `_revoked_partnerships` helper, an `ack_revoked_partnership` POST
    action, and the template must render the explicit row.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent.parent / "src/app"
    view = src / "modules/preferences/views/invitations.py"
    assert view.exists()
    view_content = view.read_text()
    assert "_revoked_partnerships" in view_content
    assert "ack_revoked_partnership" in view_content
    tpl = src / "modules/preferences/templates/pages/preferences/org_invitation.j2"
    assert "Partenariats RP terminés" in tpl.read_text()


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


# ─── #0172 ────────────────────────────────────────────────────────


def test_bug_0172_event_publish_requires_dates() -> None:
    """Bug #0172 — Sophie-Anne (2026-05-25) : « j'ai créé un événement
    qui apparaît bien dans ma liste sous le statut publié mais il
    n'apparaît pas dans EVENTS ». Root cause : the default DateFilter
    on ``/events/`` filters on ``start_datetime >= today OR
    end_datetime >= today``, and NULL >= today evaluates to NULL —
    so events published without dates land in PUBLIC but are silently
    invisible.

    Fix : require both ``start_time`` and ``end_time`` at publish
    time. Source-level check on the publish() guard.
    """
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent.parent / "src/app/modules/wip"
    event_model = src / "models/eventroom/event.py"
    assert event_model.exists()
    content = event_model.read_text()
    # The publish guard must still check start_time AND end_time.
    assert "if not self.start_time or not self.end_time" in content, (
        "Event.publish() must require both dates — bug #0172 regressed."
    )
