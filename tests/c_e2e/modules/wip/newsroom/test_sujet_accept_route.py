# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0132 part 3 — route-level coverage for the « Accepter »
action on Sujet (creates a Commande, archives the sujet, notifies the
author)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.enums import RoleEnum
from app.flask.routing import url_for
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.commande import Commande
from app.modules.wip.models.newsroom.sujet import Sujet
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _make_sujet(db_session, *, owner_id: int, media_id: int) -> Sujet:
    now = datetime.now(UTC)
    sujet = Sujet(
        owner_id=owner_id,
        media_id=media_id,
        commanditaire_id=owner_id,
        titre="Topic title",
        contenu="Topic content",
        status=PublicationStatus.PUBLIC,
        date_limite_validite=now + timedelta(days=7),
        date_parution_prevue=now + timedelta(days=14),
    )
    db_session.add(sujet)
    db_session.flush()
    return sujet


@pytest.fixture
def redac_chef(db_session: Session, test_org) -> User:
    """A rédac chef who is a member of the target media's org."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(name=RoleEnum.PRESS_MEDIA.name, description="journalist")
        db_session.add(role)
        db_session.flush()
    user = User(
        email="rc@flounet.example",
        first_name="Annick",
        last_name="Stramazian",
        active=True,
    )
    user.profile = KYCProfile()
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def author(db_session: Session) -> User:
    """The journalist author, in a different organisation."""
    author_org = Organisation(name="Fake-Le Quotient du Médecin")
    db_session.add(author_org)
    db_session.flush()
    user = User(
        email="nicolas@example.com",
        first_name="Nicolas",
        last_name="Mouriou",
        active=True,
    )
    user.organisation = author_org
    user.organisation_id = author_org.id
    db_session.add(user)
    db_session.flush()
    return user


class TestSujetAcceptRoute:
    def test_accept_creates_commande_archives_sujet_redirects_to_commandes(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author: User,
    ):
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()
        sujet_id = sujet.id

        client = make_authenticated_client(app, redac_chef)
        with patch(
            "app.modules.wip.crud.cbvs.sujets.notify_author_of_sujet_acceptance"
        ):
            response = client.get(
                url_for("SujetsWipView:accept", id=sujet.id),
                follow_redirects=False,
            )

        assert response.status_code in (302, 303)
        assert "/wip/commandes" in response.headers.get("Location", "")

        db_session.expire_all()
        # Sujet archived
        sujet_after = db_session.get(Sujet, sujet_id)
        assert sujet_after.status == PublicationStatus.ARCHIVED
        # A new Commande exists with the sujet's title.
        commandes = (
            db_session.query(Commande)
            .filter_by(titre="Topic title", media_id=test_org.id)
            .all()
        )
        assert len(commandes) == 1
        assert commandes[0].owner_id == redac_chef.id

    def test_accept_route_refuses_non_redac_chef(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        author: User,
    ):
        """A user from another org can't accept the sujet. The route
        either redirects with a flash error (when the user has
        newsroom access but not on the right media) or returns 403
        from the upstream `before_request` guard (when the user is
        in an org that has no newsroom access at all). Either way the
        sujet must NOT transition to ARCHIVED."""
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()
        sujet_id = sujet.id

        client = make_authenticated_client(app, author)
        response = client.get(
            url_for("SujetsWipView:accept", id=sujet.id),
            follow_redirects=False,
        )

        # Route either denies upstream (403) or downstream (302 with
        # flash error). What matters : the sujet state stays PUBLIC.
        assert response.status_code in (302, 303, 403)

        db_session.expire_all()
        sujet_after = db_session.get(Sujet, sujet_id)
        assert sujet_after.status == PublicationStatus.PUBLIC, (
            "unauthorized user must not archive the sujet (#0132/3)"
        )


class TestSujetPublisherTextOnEdit:
    """Bug #0132 point 3 (Erick, 2026-06-02) :

    > Si Annick Stramazian va dans le menu "Modifier", apparaît la
    > mention "Publié pour le compte de Fake-Les Editions numérique
    > du 0 et du 1" qui sort de nulle part puisque Nicolas Mouriou
    > travaille chez "Fake-Le Quotient du Médecin".

    Verifies that the #0135 fix (FormRenderer reads `model.publisher`
    instead of `g.user.organisation`) also covers the Sujet flow.
    The Sujet's `publisher_id` is populated to the author's org by
    `SujetsWipView._post_update_model` on save ; subsequent renders
    must reflect *that* org, regardless of who opens the form.
    """

    def test_redac_chef_editing_a_sujet_sees_author_org_in_header(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author: User,
    ):
        # Sujet « proposed by Nicolas to test_org » — publisher_id
        # pinned to Nicolas's org as the application would do via
        # `_post_update_model` on save.
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        sujet.publisher_id = author.organisation_id
        db_session.commit()

        client = make_authenticated_client(app, redac_chef)
        response = client.get(
            url_for("SujetsWipView:edit", id=sujet.id),
            follow_redirects=False,
        )
        assert response.status_code == 200
        body = response.data.decode()

        author_org_name = "Fake-Le Quotient du Médecin"
        redac_chef_org_name = test_org.name  # "WIP Test Organization"

        # Quotes get HTML-escaped to `&#34;` in the rendered form
        # template — assert on the unquoted name to stay readable.
        assert "Publié pour le compte de" in body
        assert author_org_name in body, (
            "the header must follow the sujet's publisher (Nicolas's "
            "org), not the editing user's org (#0132 point 3 / #0135)"
        )
        assert (
            f"Publié pour le compte de &#34;{redac_chef_org_name}&#34;" not in body
            and f'Publié pour le compte de "{redac_chef_org_name}"' not in body
        ), (
            "the rédac chef's own org must NOT leak into the "
            "'Publié pour le compte de' header (#0132 point 3)"
        )


class TestSujetAuthorMiniCardOnDetail:
    """Bug #0132 point 2 (Erick, 2026-06-02) :

    > 2- On identifie toujours très mal l'auteur. Certes, dans
    > NEWSROOM/Sujets chez Annick Stramazian, en cliquant sur "Voir",
    > il y a un encadré en bleu pâle avec la mention "Nicolas
    > Mouriou, Journaliste avec carte de presse en micro-entreprise,
    > Fake-Le quotient du Médecin". Mais on ne voit toujours pas la
    > carte résumée du journaliste avec sa photo.

    The pale-blue text-only box is replaced by the shared
    `poster_card` mini-card (photo + name + role + organisation +
    profile link + BW link if available).
    """

    @pytest.fixture
    def author_with_role(self, db_session: Session) -> User:
        role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
        if role is None:
            role = Role(name=RoleEnum.PRESS_MEDIA.name, description="journalist")
            db_session.add(role)
            db_session.flush()
        author_org = Organisation(name="Fake-Le Quotient du Médecin")
        db_session.add(author_org)
        db_session.flush()
        user = User(
            email="nicolas-pt2@example.com",
            first_name="Nicolas",
            last_name="Mouriou",
            active=True,
        )
        user.profile = KYCProfile()
        user.photo = b""
        user.organisation = author_org
        user.organisation_id = author_org.id
        user.roles.append(role)
        db_session.add(user)
        db_session.flush()
        return user

    def test_sujet_get_renders_author_mini_card(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author_with_role: User,
    ):
        sujet = _make_sujet(
            db_session, owner_id=author_with_role.id, media_id=test_org.id
        )
        sujet.publisher_id = author_with_role.organisation_id
        db_session.commit()

        client = make_authenticated_client(app, redac_chef)
        response = client.get(
            url_for("SujetsWipView:get", id=sujet.id),
            follow_redirects=False,
        )
        assert response.status_code == 200
        body = response.data.decode()

        assert "Nicolas Mouriou" in body, "author name must appear"
        assert f"/swork/members/{author_with_role.id}" in body, (
            "author mini-card must link to the profile page (#0132 pt 2)"
        )
        # The mini-card is implemented via the shared `poster_card`
        # macro — assert the macro's visual marker is present (the
        # « Voir le profil » CTA from the macro).
        assert "Voir le profil" in body, (
            "the rich poster_card macro must replace the legacy "
            "text-only blue box (#0132 pt 2)"
        )


class TestSujetAcceptSendsMailToAuthor:
    """Bug #0132 point 6 (Erick, 2026-06-02) :

    > Nicolas Mouriou n'en est pas averti. Il faudrait donc que
    > Nicolas Mouriou ait une notification d'alerte ET que la
    > commande apparaisse dans son espace WORK/NEWSROOM/Commande
    > avec la mention "Commanditaire" et la mini-carte d'Annick
    > Stramazian, rédactrice en chef de Fake-01 Flounet.

    The bell notification is already wired in via
    `notify_author_of_sujet_acceptance`. This test pins the email
    side : when the rédac chef clicks « Accepter », a
    `SujetAcceptanceNotificationMail` is sent to the original
    journalist with the « Commanditaire » mention.
    """

    def test_accept_sends_acceptance_mail_to_author(
        self,
        app: Flask,
        db_session: Session,
        test_org: Organisation,
        redac_chef: User,
        author: User,
    ):
        sujet = _make_sujet(db_session, owner_id=author.id, media_id=test_org.id)
        db_session.commit()

        sent: list[object] = []

        def fake_send(self):
            sent.append(self)

        client = make_authenticated_client(app, redac_chef)
        with (
            patch("app.modules.wip.crud.cbvs.sujets.notify_author_of_sujet_acceptance"),
            patch(
                "app.services.emails.SujetAcceptanceNotificationMail.send",
                fake_send,
            ),
        ):
            response = client.get(
                url_for("SujetsWipView:accept", id=sujet.id),
                follow_redirects=False,
            )

        assert response.status_code in (302, 303)
        assert len(sent) == 1, "exactly one acceptance mail must be sent"
        mail = sent[0]
        assert mail.recipient == author.email
        assert mail.accepter_full_name == redac_chef.full_name
        assert mail.accepter_organisation == test_org.name
        assert mail.sujet_title == "Topic title"
        assert "/wip/commandes" in mail.commande_url
