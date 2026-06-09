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
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import KYCProfile, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus
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
    # Bug #0132 pt 1 — RC visibility now requires the rédac chef
    # qualification (PM_DIR* profile OR BWMi role).
    rc.profile = KYCProfile(profile_code="PM_DIR")
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
    rc.profile = KYCProfile(profile_code="PM_DIR")
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
    rc.profile = KYCProfile(profile_code="PM_DIR")
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


# ---------------------------------------------------------------------
# Bug #0132 pt 1 (Erick, 2026-06-02) : restrict the « received Sujet »
# clause so only rédacteurs en chef of the targeted media see the
# proposal, not every member of the org. Rédac chef = either a
# `ProfileEnum.PM_DIR*` KYC profile, or an ACCEPTED BWMi / BW_OWNER
# RoleAssignment on the media's BW. Without this filter, every
# journalist at the receiving media gets every proposal — which
# Erick says destroys the targeting that journalists rely on.
# ---------------------------------------------------------------------


def _make_rc_with_profile(db_session, org, profile_code):
    user = User(
        email=f"rc-{profile_code}@example",
        first_name="Annick",
        last_name="Stramazian",
    )
    user.profile = KYCProfile(profile_code=profile_code)
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user


def _make_ordinary_journalist(db_session, org):
    user = User(
        email="aicha@example",
        first_name="Aïcha",
        last_name="BenMahfoud",
    )
    user.profile = KYCProfile(profile_code="PM_JR_CP_SAL")  # journaliste salarié
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user


def test_redac_chef_with_pm_dir_profile_sees_public_sujet(
    app, db_session: Session, media_org: Organisation, author_user: User
):
    """Bug #0132 pt 1 — Annick Stramazian (PM_DIR rédactrice en chef
    de Fake-01Flounet) voit le sujet proposé par Nicolas."""
    rc = _make_rc_with_profile(db_session, media_org, "PM_DIR")
    public = _make_sujet(
        db_session,
        media_id=media_org.id,
        owner_id=author_user.id,
        status=PublicationStatus.PUBLIC,
    )
    with app.test_request_context():
        g.user = rc
        ds = SujetDataSource(model_class=Sujet, q="")
        ids = {s.id for s in ds.get_items()}
    assert public.id in ids


def test_ordinary_journalist_does_not_see_received_sujet(
    app, db_session: Session, media_org: Organisation, author_user: User
):
    """Bug #0132 pt 1 — Aïcha BenMahfoud (PM_JR_CP_SAL journaliste
    salariée chez Fake-01Flounet) NE doit PAS voir le sujet de
    Nicolas — c'est l'attribut clé de la régression d'Erick."""
    aicha = _make_ordinary_journalist(db_session, media_org)
    public = _make_sujet(
        db_session,
        media_id=media_org.id,
        owner_id=author_user.id,
        status=PublicationStatus.PUBLIC,
    )
    with app.test_request_context():
        g.user = aicha
        ds = SujetDataSource(model_class=Sujet, q="")
        ids = {s.id for s in ds.get_items()}
    assert public.id not in ids, (
        "an ordinary journalist must NOT see Sujets received by their "
        "media's rédac chef (#0132 pt 1)"
    )


def test_other_pm_dir_variants_count_as_redac_chef(
    app, db_session: Session, media_org: Organisation, author_user: User
):
    """PM_DIR_INST and PM_DIR_SYND are also rédac chef equivalents."""
    public = _make_sujet(
        db_session,
        media_id=media_org.id,
        owner_id=author_user.id,
        status=PublicationStatus.PUBLIC,
    )
    for code in ("PM_DIR_INST", "PM_DIR_SYND"):
        rc = _make_rc_with_profile(db_session, media_org, code)
        with app.test_request_context():
            g.user = rc
            ds = SujetDataSource(model_class=Sujet, q="")
            ids = {s.id for s in ds.get_items()}
        assert public.id in ids, f"{code} must qualify as rédac chef (#0132 pt 1)"


def test_bwmi_role_holder_qualifies_as_redac_chef(
    app, db_session: Session, media_org: Organisation, author_user: User
):
    """A user without a PM_DIR profile but with an ACCEPTED BWMi
    RoleAssignment on the media's BW also counts as rédac chef
    (Erick's media-org-management equivalent)."""
    bw_owner = User(email="bw-owner@example", first_name="O", last_name="P")
    bw_owner.organisation = media_org
    bw_owner.organisation_id = media_org.id
    db_session.add(bw_owner)
    db_session.flush()
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=bw_owner.id,
        payer_id=bw_owner.id,
        organisation_id=media_org.id,
        name="Flounet BW",
    )
    db_session.add(bw)
    db_session.flush()

    rc = User(
        email="bwmi-rc@example",
        first_name="BWMi",
        last_name="Chef",
    )
    rc.organisation = media_org
    rc.organisation_id = media_org.id
    rc.profile = KYCProfile(profile_code="PM_JR_CP_SAL")  # ordinary journo
    db_session.add(rc)
    db_session.flush()
    assignment = RoleAssignment(
        business_wall_id=bw.id,
        user_id=rc.id,
        role_type=BWRoleType.BWMI.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
        invited_at=datetime.now(UTC),
        accepted_at=datetime.now(UTC),
    )
    db_session.add(assignment)
    db_session.flush()

    public = _make_sujet(
        db_session,
        media_id=media_org.id,
        owner_id=author_user.id,
        status=PublicationStatus.PUBLIC,
    )
    with app.test_request_context():
        g.user = rc
        ds = SujetDataSource(model_class=Sujet, q="")
        ids = {s.id for s in ds.get_items()}
    assert public.id in ids
