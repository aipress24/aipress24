# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `FormRenderer.publisher_text` (Bug #0135).

When a model is being edited (e.g. an Event published on behalf of a
client by a PR-agency consultant), the « Publié pour le compte de »
header on the form must reflect the model's own publisher
(`model.publisher`), not the editing user's organisation.

Erick (2026-06-02) :
    Bug pas encore résolu. Dans Event'room, on voit la phrase
    "Publié pour le compte de Fake-Les Propulseurs RP". Ce qui est
    une erreur puisque Fake-Les Propulseurs RP est la PR Agency.
    On devrait surtout voir le champ "Publier pour le compte de"
    avec [...] "Fake-Davi Logistique".

The agency is the OWNER's org ; the client is the PUBLISHER. The
header must follow the publisher.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from flask import g
from wtforms import Form, StringField

from app.flask.lib.wtforms.renderer import FormRenderer

if TYPE_CHECKING:
    from flask import Flask


class _EmptyGroupForm(Form):
    """Minimal Form with no fields rendered — only the publisher_text
    header matters for these tests."""

    class Meta:
        groups: ClassVar[dict] = {}

    name = StringField("Name")


class _StubOrg:
    def __init__(self, name: str, bw_name: str | None = None) -> None:
        self.name = name
        self.bw_name = bw_name


class _StubModel:
    def __init__(self, publisher: _StubOrg | None) -> None:
        self.id = 1
        self.publisher = publisher


class _StubUser:
    is_anonymous = False
    is_managing_another_bw = False
    selected_bw_id = None

    def __init__(self, organisation: _StubOrg | None) -> None:
        self.organisation = organisation


def _render_with_user_and_model(app: Flask, user: _StubUser, model) -> str:
    """Push a test request context with the user on g, render the
    form in edit mode, return the HTML."""
    with app.test_request_context("/wip/events/1/edit"):
        g.user = user
        renderer = FormRenderer(
            form=_EmptyGroupForm(),
            model=model,
            mode="edit",
            action_url="/wip/events/1/edit",
        )
        return str(renderer.render())


class TestPublisherTextFollowsModel:
    """When a model has its own publisher, the header must reflect it,
    NOT the editing user's organisation."""

    def test_edit_existing_event_published_for_client_shows_client_name(
        self, app: Flask
    ):
        """Bug #0135 — Igor (consultant at PR Agency Fake-Les Propulseurs)
        edits an event he published for Fake-Davi Logistique. The
        header must say « Publié pour le compte de "Fake-Davi
        Logistique" », not the agency name.
        """
        agency = _StubOrg(name="Fake-Les Propulseurs RP")
        client = _StubOrg(name="Fake-Davi Logistique")
        igor = _StubUser(organisation=agency)
        event = _StubModel(publisher=client)

        html = _render_with_user_and_model(app, igor, event)

        assert "Fake-Davi Logistique" in html, (
            "publisher_text must show the model's publisher (the client),"
            " not the editing user's org"
        )
        assert "Fake-Les Propulseurs RP" not in html, (
            "the editing user's agency name must NOT leak into the"
            " 'Publié pour le compte de' header when a model.publisher"
            " is set"
        )

    def test_edit_with_publisher_bw_name_preferred_over_org_name(self, app: Flask):
        """When the publisher org has a `bw_name`, it wins over `.name`
        (cf. existing convention for publisher rendering)."""
        client = _StubOrg(name="Fake-Davi Logistique", bw_name="Davi Logistique BW")
        user = _StubUser(organisation=_StubOrg(name="Some Agency"))
        model = _StubModel(publisher=client)

        html = _render_with_user_and_model(app, user, model)

        assert "Davi Logistique BW" in html
        assert "Some Agency" not in html

    def test_new_event_no_model_publisher_falls_back_to_user_org(self, app: Flask):
        """When creating a new model (no `publisher` yet), the
        preview falls back to the user's organisation — keeps the
        existing UX for first-time publication."""
        user_org = _StubOrg(name="Own Media SAS")
        user = _StubUser(organisation=user_org)
        # New model : publisher is None (not yet chosen).
        new_model = _StubModel(publisher=None)

        html = _render_with_user_and_model(app, user, new_model)

        assert "Own Media SAS" in html, (
            "for a new model with no publisher, the header should"
            " preview the user's own organisation"
        )

    def test_no_model_at_all_falls_back_to_user_org(self, app: Flask):
        """Same fallback when the form has no model attached."""
        user_org = _StubOrg(name="Own Media SAS")
        user = _StubUser(organisation=user_org)

        with app.test_request_context("/wip/events/new"):
            g.user = user
            renderer = FormRenderer(
                form=_EmptyGroupForm(),
                model=None,
                mode="edit",
                action_url="/wip/events/new",
            )
            html = str(renderer.render())

        assert "Own Media SAS" in html
