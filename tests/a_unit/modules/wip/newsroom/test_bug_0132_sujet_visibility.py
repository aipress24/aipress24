# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0132 (extended scope): the sujets listing must surface PUBLIC sujets
addressed to the current user's organisation, so a rédactrice en chef sees
the sujet that a journalist targeted at her media. Without this, the
publish-and-notify flow shipped earlier still left Annick (RC of
Fake-01Flounet) staring at an empty WIP/NEWSROOM list while the email had
already arrived in her inbox.

Covered: SujetDataSource._visibility_clause, _base_query, get_count.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.crud.cbvs.sujets import SujetDataSource
from app.modules.wip.models.newsroom.sujet import Sujet

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def media_org(db_session: Session) -> Organisation:
    org = Organisation(name="Fake-01 Flounet")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def author_user(db_session: Session) -> User:
    user = User(email="nicolas@example.com", first_name="Nicolas", last_name="Moriou")
    db_session.add(user)
    db_session.flush()
    return user


def _make_sujet(
    db_session: Session,
    *,
    media_id: int,
    owner_id: int,
    titre: str = "Mon enquête",
    contenu: str = "Brief de l'enquête",
    status: PublicationStatus = PublicationStatus.DRAFT,
) -> Sujet:
    sujet = Sujet(
        titre=titre,
        contenu=contenu,
        date_limite_validite=dt.datetime(2026, 12, 31, tzinfo=dt.UTC),
        date_parution_prevue=dt.datetime(2027, 1, 31, tzinfo=dt.UTC),
        media_id=media_id,
        owner_id=owner_id,
        commanditaire_id=owner_id,
    )
    sujet.status = status  # type: ignore[assignment]
    db_session.add(sujet)
    db_session.flush()
    return sujet


def test_owner_only_when_user_has_no_organisation(
    app, db_session: Session, media_org: Organisation, author_user: User
):
    author_user.organisation_id = None
    db_session.flush()
    own = _make_sujet(db_session, media_id=media_org.id, owner_id=author_user.id)
    with app.test_request_context():
        g.user = author_user
        ds = SujetDataSource(model_class=Sujet, q="")
        items = ds.get_items()
        assert own in items


def test_rc_sees_public_sujet_targeting_her_media(
    app, db_session: Session, media_org: Organisation, author_user: User
):
    rc = User(email="rc@flounet.example", first_name="Annick", last_name="S")
    rc.organisation_id = media_org.id
    db_session.add(rc)
    db_session.flush()

    public_sujet = _make_sujet(
        db_session,
        media_id=media_org.id,
        owner_id=author_user.id,
        status=PublicationStatus.PUBLIC,
    )
    # A draft to the same media must NOT surface for the RC.
    draft_sujet = _make_sujet(
        db_session,
        media_id=media_org.id,
        owner_id=author_user.id,
        titre="Draft",
        status=PublicationStatus.DRAFT,
    )

    with app.test_request_context():
        g.user = rc
        ds = SujetDataSource(model_class=Sujet, q="")
        items = ds.get_items()
        ids = {s.id for s in items}
        assert public_sujet.id in ids
        assert draft_sujet.id not in ids


def test_rc_does_not_see_other_medias_public_sujets(
    app, db_session: Session, media_org: Organisation, author_user: User
):
    other_media = Organisation(name="Other Media")
    db_session.add(other_media)
    db_session.flush()

    rc = User(email="rc2@example", first_name="A", last_name="B")
    rc.organisation_id = media_org.id
    db_session.add(rc)
    db_session.flush()

    unrelated = _make_sujet(
        db_session,
        media_id=other_media.id,
        owner_id=author_user.id,
        status=PublicationStatus.PUBLIC,
    )

    with app.test_request_context():
        g.user = rc
        ds = SujetDataSource(model_class=Sujet, q="")
        items = ds.get_items()
        assert unrelated not in items


def test_owner_sees_their_own_drafts(
    app, db_session: Session, media_org: Organisation, author_user: User
):
    author_user.organisation_id = media_org.id  # author IS in some org
    db_session.flush()
    own_draft = _make_sujet(
        db_session,
        media_id=media_org.id,
        owner_id=author_user.id,
        status=PublicationStatus.DRAFT,
    )
    with app.test_request_context():
        g.user = author_user
        ds = SujetDataSource(model_class=Sujet, q="")
        items = ds.get_items()
        assert own_draft in items


def test_get_count_matches_get_items(
    app, db_session: Session, media_org: Organisation, author_user: User
):
    rc = User(email="rc3@example", first_name="A", last_name="B")
    rc.organisation_id = media_org.id
    db_session.add(rc)
    db_session.flush()
    _make_sujet(
        db_session,
        media_id=media_org.id,
        owner_id=author_user.id,
        status=PublicationStatus.PUBLIC,
    )
    _make_sujet(
        db_session,
        media_id=media_org.id,
        owner_id=author_user.id,
        titre="Draft - hidden from RC",
        status=PublicationStatus.DRAFT,
    )

    with app.test_request_context():
        g.user = rc
        ds = SujetDataSource(model_class=Sujet, q="")
        assert ds.get_count() == len(ds.get_items())
