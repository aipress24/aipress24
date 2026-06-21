# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP opportunities pages."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from attr import frozen
from flask import (
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from svcs.flask import container
from werkzeug import Response
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.flask.lib.htmx import extract_fragment
from app.flask.lib.nav import nav
from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation.user_utils import (
    get_selected_business_wall_for_user,
)
from app.modules.wip import blueprint
from app.modules.wip.services.newsroom import AvisEnqueteService
from app.services.emails import ContactAvisEnqueteAcceptanceMail

if TYPE_CHECKING:
    from app.modules.wip.models.newsroom.avis_enquete import (
        AvisEnquete,
        ContactAvisEnquete,
    )

from ._common import get_secondary_menu

_OPPORTUNITES_TABS = (
    ("avis", "Avis d'enquête"),
    ("missions", "Missions"),
    ("projects", "Projets"),
    ("jobs", "Emplois"),
)

_MARKETPLACE_TAB_LABELS: dict[str, tuple[str, str]] = {
    "missions": ("Mission", "missions_detail"),
    "projects": ("Projet", "projects_detail"),
    "jobs": ("Emploi", "jobs_detail"),
}

_STATUS_TO_FORM_FIELD: dict[str, tuple[str, str]] = {
    # Pure mapping : StatutAvis value → (reponse1 token, prefill key).
    # Prefill key is the form-state field that should receive the
    # contact's `rdv_notes_expert` value when the contact already has
    # this status.
    "accepte": ("oui", "contribution"),
    "accepte_relation_presse": ("oui_relation_presse", "contribution"),
    "refuse": ("non", "refusal_reason"),
    "refuse_suggestion": ("non-mais", "suggestion"),
}


def _build_opportunites_tabs(current: str) -> list[dict]:
    return [
        {
            "id": tab_id,
            "label": label,
            "href": url_for("wip.opportunities", tab=tab_id)
            if tab_id != "avis"
            else url_for("wip.opportunities"),
            "active": current == tab_id,
        }
        for tab_id, label in _OPPORTUNITES_TABS
    ]


def _pick_protocol(domain: str) -> str:
    """Pure : pick http for loopback `127.x.x.x`, https everywhere else.

    Used to compose absolute URLs that travel through emails or
    notifications. Loopback domains can't speak TLS in dev, so we
    downgrade only for them.
    """
    return "http" if domain.startswith("127.") else "https"


def _build_absolute_url(domain: str, path: str) -> str:
    """Pure : compose `<protocol>://<domain><path>`."""
    return f"{_pick_protocol(domain)}://{domain}{path}"


def _translate_response_label(response: str) -> str:
    """Pure : map the raw response token to its human label.

    Currently only `oui_relation_presse` is rewritten — every other
    token is forwarded unchanged.
    """
    if response == "oui_relation_presse":
        return "oui, avec relation presse"
    return response


def _select_press_officer_email(picked: str, valid_emails: list[str]) -> str:
    """Pure : choose which press-officer email to record on the contact.

    Bug #0075/2 — when the form rendered multiple options, trust the
    user's pick if (and only if) it appears in the valid set. Fall
    back to the first valid email when the form didn't carry an
    explicit choice (single-option case). When neither holds, leave
    the field empty.
    """
    picked = (picked or "").strip()
    if picked and picked in valid_emails:
        return picked
    if valid_emails:
        return valid_emails[0]
    return ""


def _form_defaults_from_status(status: str, rdv_notes_expert: str) -> dict[str, str]:
    """Pure : derive the form-state defaults for a contact's status.

    Returns a complete dict with the four prefill keys :
    `reponse1`, `contribution`, `refusal_reason`, `suggestion`.
    Only one of the three text fields is populated (per the status
    spec) ; the others are empty. Unknown / EN_ATTENTE statuses
    return all-empty.
    """
    base = {
        "reponse1": "",
        "contribution": "",
        "refusal_reason": "",
        "suggestion": "",
    }
    if status not in _STATUS_TO_FORM_FIELD:
        return base
    reponse1, prefill_key = _STATUS_TO_FORM_FIELD[status]
    base["reponse1"] = reponse1
    base[prefill_key] = rdv_notes_expert or ""
    return base


def _marketplace_labels(tab: str) -> tuple[str, str]:
    """Pure : (human label, biz detail endpoint name) for a tab id."""
    return _MARKETPLACE_TAB_LABELS[tab]


@blueprint.route("/opportunities")
@nav(icon="cake")
def opportunities():
    """Opportunités — Avis d'enquête (default) + 3 marketplace tabs.

    Bug #0188 (Erick, 2026-06-04) : « les répondants ne veulent pas
    que tout le monde voie leurs propositions. [...] les réponses
    doivent alors s'afficher tant du côté annonceur que du côté
    répondant, dans WORK/OPPORTUNITÉS/Missions / Projects / Job
    Board. » Each marketplace tab shows the current user's own
    candidacies + the candidacies they received on their offers.
    """
    tab = request.args.get("tab", "avis")
    if tab in {"missions", "projects", "jobs"}:
        return _render_marketplace_opportunites_tab(tab)
    return _render_avis_opportunites_tab()


def _render_avis_opportunites_tab():
    # Lazy import to avoid circular import
    from app.modules.wip.models import ContactAvisEnquete

    # Filter in SQL (was: load ALL contacts then `c.expert == g.user` in
    # Python, which lazy-loaded every contact's expert — N+1). Eager-load the
    # avis (sort + title) and the journalist + their org (shown on each card).
    stmt = (
        select(ContactAvisEnquete)
        .where(ContactAvisEnquete.expert_id == g.user.id)
        .options(
            selectinload(ContactAvisEnquete.avis_enquete),
            selectinload(ContactAvisEnquete.journaliste).selectinload(
                User.organisation
            ),
        )
    )
    contacts = list(db.session.scalars(stmt))

    contacts.sort(key=lambda c: c.avis_enquete.date_fin_enquete, reverse=True)
    contacts = contacts[:50]

    return render_template(
        "wip/pages/opportunities.j2",
        title="Mes opportunités",
        contacts=contacts,
        tabs=_build_opportunites_tabs("avis"),
        menus={"secondary": get_secondary_menu("opportunities")},
    )


def _render_marketplace_opportunites_tab(tab: str):
    """Bug #0188 — render the marketplace tab (missions / projects /
    jobs). Shows two sections : « Mes candidatures » (the user is the
    applicant) and « Candidatures reçues » (the user is the offer's
    owner)."""
    # Lazy import to avoid bringing biz models into the WIP startup.
    from sqlalchemy import select

    from app.flask.extensions import db
    from app.modules.biz.models import (
        JobOffer,
        MissionOffer,
        OfferApplication,
        ProjectOffer,
    )

    offer_models = {
        "missions": MissionOffer,
        "projects": ProjectOffer,
        "jobs": JobOffer,
    }
    offer_model = offer_models[tab]
    user = g.user

    if getattr(user, "is_anonymous", False):
        return redirect(url_for("security.login", next=request.path))

    sent_stmt = (
        select(OfferApplication, offer_model)
        .join(offer_model, OfferApplication.offer_id == offer_model.id)
        .where(OfferApplication.owner_id == user.id)
        .order_by(OfferApplication.created_at.desc())
    )
    sent_applications = list(db.session.execute(sent_stmt).all())

    received_stmt = (
        select(OfferApplication, offer_model)
        .join(offer_model, OfferApplication.offer_id == offer_model.id)
        .where(offer_model.owner_id == user.id)
        .order_by(OfferApplication.created_at.desc())
    )
    received_applications = list(db.session.execute(received_stmt).all())

    offer_label, detail_endpoint = _marketplace_labels(tab)

    return render_template(
        "wip/pages/opportunities_marketplace.j2",
        title="Mes opportunités",
        tabs=_build_opportunites_tabs(tab),
        tab_id=tab,
        offer_label=offer_label,
        detail_endpoint=f"biz.{detail_endpoint}",
        sent_applications=sent_applications,
        received_applications=received_applications,
        menus={"secondary": get_secondary_menu("opportunities")},
    )


@blueprint.route("/opportunities/<int:id>")
def media_opportunity(id: int):
    """Opportunité média.

    Reached from the avis-d'enquête notification email. Three failure
    paths used to all return an empty body (blank page in the
    browser) — fix by redirecting to actionable surfaces instead:

    - Anonymous visitor → the login page, with a `next=` so they
      land back on this URL after auth.
    - Authenticated as the wrong user → a flash + the opportunities
      list (we can't show them another expert's opportunity).
    - Unknown contact id → 404 (e.g. id from an old email after
      the contact was deleted).
    """
    from app.modules.wip.models import ContactAvisEnqueteRepository

    if g.user.is_anonymous:
        return redirect(url_for("security.login", next=request.path))

    repo = container.get(ContactAvisEnqueteRepository)
    # `repo.get(id)` raises NotFoundError on unknown ids — use the
    # `_or_none` variant so we can issue a clean 404 instead of a
    # 500 with a stack trace.
    contact = repo.get_one_or_none(id=id)
    if contact is None:
        raise NotFound
    if g.user.id != contact.expert_id:
        flash(
            "Cet avis d'enquête ne vous est pas adressé. "
            "Voici vos opportunités personnelles.",
            "warning",
        )
        return redirect(url_for("wip.opportunities"))

    html = _render_media_opportunity(id)
    html = extract_fragment(html, id="form")
    return html


def send_avis_enquete_acceptance_email(
    contact: ContactAvisEnquete,
    response: str,
) -> None:
    """
    Send notification emails to journalist about an Avis d'Enquête
    acceptance of the contacted expert.

    Args:
        contact: ContactAvisEnquete
        expert: User responding
        response: either "oui", "oui_relation_presse", "non", "non-mais"
        notes: response notes of the expert
    """
    expert = cast(User, current_user)
    if expert.is_anonymous:
        return
    sender_mail = expert.email
    sender_full_name = expert.full_name

    recipient = contact.journaliste.email
    title = contact.avis_enquete.titre
    notes = contact.rdv_notes_expert

    response = _translate_response_label(response)

    notification_mail = ContactAvisEnqueteAcceptanceMail(
        sender="contact@aipress24.com",
        recipient=recipient,
        sender_mail=sender_mail,  # expert
        sender_full_name=sender_full_name,
        title=title,  # avis title
        response=response,
        notes=notes,
    )
    notification_mail.send()


@blueprint.route("/opportunities/<int:id>", methods=["POST"])
def media_opportunity_post(id: int) -> str | Response:
    """Handle media opportunity form submission."""
    # Lazy import to avoid circular import
    from app.modules.wip.models import ContactAvisEnqueteRepository, StatutAvis

    expert = cast(User, current_user)
    if expert.is_anonymous:
        return ""

    repo = container.get(ContactAvisEnqueteRepository)
    # `repo.get(id)` raises Advanced-Alchemy `NotFoundError` (not the
    # werkzeug 404) on a stale/forged id → unhandled 500. Mirror the
    # GET sibling (`media_opportunity`, ~line 89): `_or_none` + 404.
    # Audit C4 / lessons-learned #15.
    contact = repo.get_one_or_none(id=id)
    if contact is None:
        raise NotFound

    # Bug #0164: a response is only meaningful once the user's org has
    # an active Business Wall. Before this guard, the POST silently
    # mutated the contact and the user came back to find the answer
    # "lost". Refuse here so the GET banner remains the single source
    # of truth on the prerequisite.
    if get_selected_business_wall_for_user(expert) is None:
        flash(
            "Vous devez configurer un Business Wall actif avant de "
            "répondre à un avis d'enquête.",
            "warning",
        )
        return redirect(url_for("wip.media_opportunity", id=id))

    reponse = request.form.get("reponse1")
    if reponse:
        contact.date_reponse = datetime.now(UTC)
        if reponse == "oui":
            contact.status = StatutAvis.ACCEPTE  # type: ignore[assignment]
            contact.rdv_notes_expert = request.form.get("contribution", "")
        elif reponse == "oui_relation_presse":
            contact.status = StatutAvis.ACCEPTE_RELATION_PRESSE  # type: ignore[assignment]
            contact.rdv_notes_expert = request.form.get("contribution", "")
            # Bug #0061-b: resolve the org's accepted BWPRi, not the
            # expert's own profile field (gave the PDG's own email).
            # Bug #0075/2: when the form rendered a dropdown of multiple
            # press contacts (internal + external partners), trust the
            # user's pick. Validate it against the current valid set so
            # a tampered POST can't slip in an arbitrary address. Fall
            # back to the first emitted email if the form didn't carry
            # an explicit choice (single-option case).
            svc = AvisEnqueteService()
            valid_emails = svc.press_officer_emails(expert)
            picked = request.form.get("email_relation_presse") or ""
            contact.email_relation_presse = _select_press_officer_email(
                picked, valid_emails
            )

            # Bug #0071 / #0174 (Erick, 2026-05-26): also chain a new
            # ContactAvisEnquete for the picked press officer so they
            # actually receive the mail + in-app notification — the
            # previous code only stored the email but never propagated.
            if contact.email_relation_presse:

                def _build_pr_opportunity_url(c: ContactAvisEnquete) -> str:
                    domain = str(current_app.config.get("SERVER_NAME"))
                    path = str(url_for("wip.media_opportunity", id=c.id))
                    return _build_absolute_url(domain, path)

                try:
                    svc.associate_press_officer(
                        contact=contact,
                        press_officer_email=contact.email_relation_presse,
                        url_builder=_build_pr_opportunity_url,
                    )
                except ValueError as e:
                    # Should not happen — `picked` was just validated
                    # above against `valid_emails`. Log and continue
                    # rather than blocking the response.
                    warn(
                        f"associate_press_officer failed for contact "
                        f"{contact.id}, email={contact.email_relation_presse!r}: {e}"
                    )
        elif reponse == "non":
            contact.status = StatutAvis.REFUSE  # type: ignore[assignment]
            contact.rdv_notes_expert = request.form.get("refusal_reason", "")
        elif reponse == "non-mais":
            try:
                suggested_id = int(request.form.get("suggested_colleague_id", ""))
            except ValueError:
                flash(
                    "Merci de sélectionner un collègue dans la liste.",
                    "error",
                )
                return redirect(url_for("wip.opportunities"))

            colleague_user = repo.session.get(User, suggested_id)
            if colleague_user is None:
                flash("Collègue introuvable.", "error")
                return redirect(url_for("wip.opportunities"))

            def _build_opportunity_url(contact: ContactAvisEnquete) -> str:
                domain = str(current_app.config.get("SERVER_NAME"))
                path = str(url_for("wip.media_opportunity", id=contact.id))
                return _build_absolute_url(domain, path)

            avis_service = AvisEnqueteService()
            try:
                avis_service.suggest_colleague(
                    contact=contact,
                    colleague=colleague_user,
                    url_builder=_build_opportunity_url,
                )
            except ValueError as e:
                flash(str(e), "error")
                return redirect(url_for("wip.opportunities"))

            contact.status = StatutAvis.REFUSE_SUGGESTION  # type: ignore[assignment]
            contact.rdv_notes_expert = f"Suggéré: {colleague_user.full_name}"

        send_avis_enquete_acceptance_email(contact, reponse)

        repo.session.commit()

    return redirect(url_for("wip.opportunities"))


@blueprint.route("/opportunities/<int:id>/form", methods=["POST"])
def media_opportunity_form_update(id: int) -> str | Response:
    """Handle media opportunity form partial updates for HTMX.

    Security VERIFY-002 : the form fragment is prefilled with the
    contact's `rdv_notes_expert` and the expert's press-officer email
    list — never render it for a contact that doesn't belong to the
    requesting user. The GET sibling (`media_opportunity`) already
    enforces this ; the HTMX POST partial used to skip the check.
    """
    from app.modules.wip.models import ContactAvisEnqueteRepository

    if g.user.is_anonymous:
        raise NotFound
    repo = container.get(ContactAvisEnqueteRepository)
    contact = repo.get_one_or_none(id=id)
    if contact is None:
        raise NotFound
    if g.user.id != contact.expert_id:
        raise NotFound

    html = _render_media_opportunity(id)
    html = extract_fragment(html, id="avis-response-form")
    return html


def _render_media_opportunity(id: int) -> str:
    """Render the media opportunity template."""
    # Lazy import to avoid circular import
    from app.modules.wip.models import ContactAvisEnqueteRepository, StatutAvis

    repo = container.get(ContactAvisEnqueteRepository)
    # Same raises-vs-None contract as media_opportunity_post — a
    # stale id from an old HTMX form must 404, not 500.
    # Audit C4 / lessons-learned #15.
    contact = repo.get_one_or_none(id=id)
    if contact is None:
        raise NotFound
    media_opp = MediaOpportunity(
        id=contact.id,
        avis_enquete=contact.avis_enquete,
        journaliste=contact.journaliste,
    )

    expert = cast(User, current_user)
    if expert.is_anonymous:
        return ""

    avis_service = AvisEnqueteService()
    # Bug #0061-b: prefill with the org's accepted BWPRi email.
    # Bug #0075/2: full list (internal BWPRi + external BWPRe partners)
    # so the form can render a dropdown when the org has more than one
    # press contact.
    press_officer_emails = avis_service.press_officer_emails(expert)
    email_relation_presse = press_officer_emails[0] if press_officer_emails else ""

    defaults = _form_defaults_from_status(
        str(contact.status), contact.rdv_notes_expert or ""
    )

    form_state = {
        "reponse1": request.form.get("reponse1", defaults["reponse1"]),
        "contribution": request.form.get("contribution", defaults["contribution"]),
        "refusal_reason": request.form.get(
            "refusal_reason", defaults["refusal_reason"]
        ),
        "suggestion": request.form.get("suggestion", defaults["suggestion"]),
        "suggested_colleague_id": request.form.get("suggested_colleague_id", ""),
        "email_relation_presse": email_relation_presse,
        "press_officer_emails": press_officer_emails,
    }

    is_answered = contact.status != StatutAvis.EN_ATTENTE
    eligible_colleagues = avis_service.list_eligible_colleagues(contact)
    # Bug #0164: gate the response form on having an active BW so the
    # user is not invited to type an answer that won't persist.
    requires_bw = get_selected_business_wall_for_user(expert) is None

    return render_template(
        "wip/pages/media_opportunity.j2",
        title="Opportunité média",
        media_opp=media_opp,
        contact=contact,
        form_state=form_state,
        is_answered=is_answered,
        requires_bw=requires_bw,
        eligible_colleagues=eligible_colleagues,
        menus={"secondary": get_secondary_menu("opportunities")},
    )


@frozen
class MediaOpportunity:
    """Media opportunity data."""

    id: int
    journaliste: User
    avis_enquete: AvisEnquete

    @property
    def titre(self) -> str:
        return self.avis_enquete.titre

    @property
    def brief(self) -> str:
        return self.avis_enquete.contenu
