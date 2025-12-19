# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP opportunities pages."""

from __future__ import annotations

from attr import frozen
from flask import g, render_template, request
from svcs.flask import container
from werkzeug import Response

from app.flask.lib.htmx import extract_fragment
from app.models.auth import User
from app.modules.wip import blueprint

from ._common import get_secondary_menu


@blueprint.route("/opportunities")
def opportunities():
    """Opportunités"""
    # Lazy import to avoid circular import
    from app.modules.wip.models import AvisEnquete, ContactAvisEnqueteRepository

    repo = container.get(ContactAvisEnqueteRepository)
    contacts = repo.list()
    contacts = [contact for contact in contacts if contact.expert == g.user]

    media_opportunities = []
    for contact in contacts:
        avis_enquete: AvisEnquete = contact.avis_enquete
        media_opp = MediaOpportunity(
            id=contact.id,
            avis_enquete=avis_enquete,
            journaliste=contact.journaliste,
        )
        media_opportunities.append(media_opp)

    return render_template(
        "wip/pages/opportunities.j2",
        title="Mes opportunités",
        media_opportunities=media_opportunities,
        menus={"secondary": get_secondary_menu("opportunities")},
    )


@blueprint.route("/opportunities/<int:id>")
def media_opportunity(id: int):
    """Opportunité média"""
    html = _render_media_opportunity(id)
    html = extract_fragment(html, id="form")
    return html


@blueprint.route("/opportunities/<int:id>", methods=["POST"])
def media_opportunity_post(id: int) -> str | Response:
    """Handle media opportunity form submission."""
    html = _render_media_opportunity(id)
    html = extract_fragment(html, id="form")
    return html


def _render_media_opportunity(id: int) -> str:
    """Render the media opportunity template."""
    # Lazy import to avoid circular import
    from app.modules.wip.models import ContactAvisEnqueteRepository

    repo = container.get(ContactAvisEnqueteRepository)
    contact = repo.get(id)
    media_opp = MediaOpportunity(
        id=contact.id,
        avis_enquete=contact.avis_enquete,
        journaliste=contact.journaliste,
    )
    form_state = {
        "reponse1": request.form.get("reponse1", ""),
    }
    return render_template(
        "wip/pages/media_opportunity.j2",
        title="Opportunité média",
        media_opp=media_opp,
        form_state=form_state,
        menus={"secondary": get_secondary_menu("media_opportunity")},
    )


@frozen
class MediaOpportunity:
    """Media opportunity data."""

    id: int
    journaliste: User
    avis_enquete: object

    @property
    def titre(self):
        return self.avis_enquete.titre
