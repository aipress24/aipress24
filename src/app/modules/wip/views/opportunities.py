# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP opportunities pages."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from attr import frozen
from flask import (
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from svcs.flask import container
from werkzeug import Response

from app.flask.lib.htmx import extract_fragment
from app.flask.lib.nav import nav
from app.models.auth import User
from app.modules.bw.bw_activation.user_utils import get_business_wall_for_user
from app.modules.wip import blueprint
from app.modules.wip.services.newsroom import AvisEnqueteService
from app.services.emails import ContactAvisEnqueteAcceptanceMail

if TYPE_CHECKING:
    from app.modules.wip.models.newsroom.avis_enquete import (
        AvisEnquete,
        ContactAvisEnquete,
    )

from ._common import get_secondary_menu


@blueprint.route("/opportunities")
@nav(icon="cake")
def opportunities():
    """Opportunités"""
    # Lazy import to avoid circular import
    from app.modules.wip.models import ContactAvisEnqueteRepository

    repo = container.get(ContactAvisEnqueteRepository)
    contacts = repo.list()
    contacts = [contact for contact in contacts if contact.expert == g.user]

    contacts.sort(key=lambda c: c.avis_enquete.date_fin_enquete, reverse=True)
    contacts = contacts[:50]

    return render_template(
        "wip/pages/opportunities.j2",
        title="Mes opportunités",
        contacts=contacts,
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
        abort(404)
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

    if response == "oui_relation_presse":
        response = "oui, avec relation presse"

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
        abort(404)

    # Bug #0164: a response is only meaningful once the user's org has
    # an active Business Wall. Before this guard, the POST silently
    # mutated the contact and the user came back to find the answer
    # "lost". Refuse here so the GET banner remains the single source
    # of truth on the prerequisite.
    if get_business_wall_for_user(expert) is None:
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
            contact.email_relation_presse = AvisEnqueteService().press_officer_email(
                expert
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
                if domain.startswith("127."):
                    protocol = "http"
                else:
                    protocol = "https"
                # url = str(url_for("wip.media_opportunity", id=contact.id, _external=True))
                path = str(url_for("wip.media_opportunity", id=contact.id))
                return f"{protocol}://{domain}{path}"

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
    """Handle media opportunity form partial updates for HTMX."""
    # This view does NOT save anything. It just renders the form.
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
        abort(404)
    media_opp = MediaOpportunity(
        id=contact.id,
        avis_enquete=contact.avis_enquete,
        journaliste=contact.journaliste,
    )

    expert = cast(User, current_user)
    if expert.is_anonymous:
        return ""

    reponse1 = ""
    contribution = ""
    refusal_reason = ""
    suggestion = ""
    avis_service = AvisEnqueteService()
    # Bug #0061-b: prefill with the org's accepted BWPRi email.
    email_relation_presse = avis_service.press_officer_email(expert)

    if contact.status == StatutAvis.ACCEPTE:
        reponse1 = "oui"
        contribution = contact.rdv_notes_expert or ""
    elif contact.status == StatutAvis.ACCEPTE_RELATION_PRESSE:
        reponse1 = "oui_relation_presse"
        contribution = contact.rdv_notes_expert or ""
    elif contact.status == StatutAvis.REFUSE:
        reponse1 = "non"
        refusal_reason = contact.rdv_notes_expert or ""
    elif contact.status == StatutAvis.REFUSE_SUGGESTION:
        reponse1 = "non-mais"
        suggestion = contact.rdv_notes_expert or ""

    form_state = {
        "reponse1": request.form.get("reponse1", reponse1),
        "contribution": request.form.get("contribution", contribution),
        "refusal_reason": request.form.get("refusal_reason", refusal_reason),
        "suggestion": request.form.get("suggestion", suggestion),
        "suggested_colleague_id": request.form.get("suggested_colleague_id", ""),
        "email_relation_presse": email_relation_presse,
    }

    is_answered = contact.status != StatutAvis.EN_ATTENTE
    eligible_colleagues = avis_service.list_eligible_colleagues(contact)
    # Bug #0164: gate the response form on having an active BW so the
    # user is not invited to type an answer that won't persist.
    requires_bw = get_business_wall_for_user(expert) is None

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
