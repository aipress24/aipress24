# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import frozen
from flask import g, request
from svcs.flask import container
from werkzeug import Response

from app.flask.lib.htmx import extract_fragment
from app.flask.lib.pages import page
from app.models.auth import User
from app.modules.wip.models import AvisEnquete, ContactAvisEnqueteRepository

from .base import BaseWipPage
from .home import HomePage

__all__ = ["OpportunitiesPage"]


@frozen
class MediaOpportunity:
    id: int
    journaliste: User
    avis_enquete: AvisEnquete

    @property
    def titre(self):
        return self.avis_enquete.titre


@page
class OpportunitiesPage(BaseWipPage):
    name = "opportunities"
    label = "Opportunités"
    title = "Mes opportunités"
    icon = "cake"

    parent = HomePage

    def context(self):
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

        ctx = {
            "media_opportunities": media_opportunities,
        }
        return ctx


@page
class MediaOpportunityPage(BaseWipPage):
    name = "media_opportunity"
    label = "Opportunité média"
    title = "Opportunité média"

    path = "/opportunities/<int:id>"

    parent = OpportunitiesPage

    def __init__(self, id: int) -> None:
        self.id = id
        self.args = {"id": id}

    def get(self) -> str | Response:
        html = self.render()
        html = extract_fragment(html, id="form")
        return html

    post = get

    def context(self):
        repo = container.get(ContactAvisEnqueteRepository)
        contact = repo.get(self.id)
        media_opp = MediaOpportunity(
            id=contact.id,
            avis_enquete=contact.avis_enquete,
            journaliste=contact.journaliste,
        )
        form_state = {
            "reponse1": request.form.get("reponse1", ""),
        }
        ctx = {
            "media_opp": media_opp,
            "form_state": form_state,
        }
        return ctx
