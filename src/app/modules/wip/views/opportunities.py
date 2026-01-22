# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP opportunities pages."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from attr import frozen
from flask import g, redirect, render_template, request, url_for
from flask_login import current_user
from svcs.flask import container
from werkzeug import Response

from app.flask.lib.htmx import extract_fragment
from app.flask.lib.nav import nav
from app.models.auth import User
from app.modules.wip import blueprint
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
    """Opportunité média"""
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
        response: either "oui", "non", "non-mais"
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

    repo = container.get(ContactAvisEnqueteRepository)
    contact = repo.get(id)

    reponse = request.form.get("reponse1")
    if reponse:
        contact.date_reponse = datetime.now(UTC)
        if reponse == "oui":
            contact.status = StatutAvis.ACCEPTE  # type: ignore[assignment]
            contact.rdv_notes_expert = request.form.get("contribution", "")
        elif reponse == "non":
            contact.status = StatutAvis.REFUSE  # type: ignore[assignment]
        elif reponse == "non-mais":
            contact.status = StatutAvis.REFUSE_SUGGESTION  # type: ignore[assignment]
            contact.rdv_notes_expert = request.form.get("suggestion", "")

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
    contact = repo.get(id)
    media_opp = MediaOpportunity(
        id=contact.id,
        avis_enquete=contact.avis_enquete,
        journaliste=contact.journaliste,
    )
    reponse1 = ""
    contribution = ""
    suggestion = ""

    if contact.status == StatutAvis.ACCEPTE:
        reponse1 = "oui"
        contribution = contact.rdv_notes_expert or ""
    elif contact.status == StatutAvis.REFUSE:
        reponse1 = "non"
    elif contact.status == StatutAvis.REFUSE_SUGGESTION:
        reponse1 = "non-mais"
        suggestion = contact.rdv_notes_expert or ""

    form_state = {
        "reponse1": request.form.get("reponse1", reponse1),
        "contribution": request.form.get("contribution", contribution),
        "suggestion": request.form.get("suggestion", suggestion),
    }

    is_answered = contact.status != StatutAvis.EN_ATTENTE

    return render_template(
        "wip/pages/media_opportunity.j2",
        title="Opportunité média",
        media_opp=media_opp,
        contact=contact,
        form_state=form_state,
        is_answered=is_answered,
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
