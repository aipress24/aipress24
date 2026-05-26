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
