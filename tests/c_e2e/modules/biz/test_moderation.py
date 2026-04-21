# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end tests for v0.4 — moderation gate + admin dashboard."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.biz.models import MissionOffer, MissionStatus
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"mod_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def _roles(db_session: Session) -> tuple[Role, Role]:
    press = Role(
        name=RoleEnum.PRESS_MEDIA.name,
        description=RoleEnum.PRESS_MEDIA.value,
    )
    admin = Role(
        name=RoleEnum.ADMIN.name,
        description=RoleEnum.ADMIN.value,
    )
    db_session.add_all([press, admin])
    db_session.commit()
    return press, admin


@pytest.fixture
def emitter(db_session: Session, _roles) -> User:
    press, _ = _roles
    org = Organisation(name="Moderation Test Org")
    db_session.add(org)
    db_session.commit()

    user = User(email=_unique_email(), active=True)
    user.photo = b""
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(press)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def admin(db_session: Session, _roles) -> User:
    press, admin_role = _roles
    user = User(email=_unique_email(), active=True)
    user.photo = b""
    user.roles.append(press)
    user.roles.append(admin_role)
    db_session.add(user)
    db_session.commit()
    return user


def test_new_mission_goes_to_pending_when_moderation_on(
    app: Flask, db_session: Session, emitter: User
):
    app.config["MARKETPLACE_MODERATION_REQUIRED"] = True
    try:
        client = make_authenticated_client(app, emitter)
        client.post(
            "/biz/missions/new",
            data={
                "title": "Mission en modération",
                "description": "Description test suffisamment longue.",
            },
        )
        mission = (
            db_session.query(MissionOffer)
            .filter_by(title="Mission en modération")
            .first()
        )
        assert mission is not None
        assert mission.status == PublicationStatus.PENDING
    finally:
        app.config["MARKETPLACE_MODERATION_REQUIRED"] = False


def test_pending_offer_hidden_from_listing(
    app: Flask, db_session: Session, emitter: User
):
    mission = MissionOffer(
        title="Hidden pending mission",
        description="x",
        status=PublicationStatus.PENDING,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
    )
    db_session.add(mission)
    db_session.commit()

    client = make_authenticated_client(app, emitter)
    response = client.get("/biz/?current_tab=missions")
    assert response.status_code == 200
    assert b"Hidden pending mission" not in response.data


def test_pending_offer_visible_to_owner(app: Flask, db_session: Session, emitter: User):
    mission = MissionOffer(
        title="Owner can see pending",
        description="x",
        status=PublicationStatus.PENDING,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
    )
    db_session.add(mission)
    db_session.commit()

    client = make_authenticated_client(app, emitter)
    response = client.get(f"/biz/missions/{mission.id}")
    assert response.status_code == 200


def test_pending_offer_invisible_to_other_user(
    app: Flask, db_session: Session, emitter: User, admin: User
):
    mission = MissionOffer(
        title="Hidden from strangers",
        description="x",
        status=PublicationStatus.PENDING,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
    )
    db_session.add(mission)
    db_session.commit()

    # admin logged in as a regular biz user hitting /biz/missions/<id>
    other_client = make_authenticated_client(app, admin)
    response = other_client.get(f"/biz/missions/{mission.id}")
    assert response.status_code == 404


def test_admin_moderation_queue_lists_pending(
    app: Flask, db_session: Session, emitter: User, admin: User
):
    mission = MissionOffer(
        title="Moderation queue entry",
        description="Long enough description for the queue page.",
        status=PublicationStatus.PENDING,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
    )
    db_session.add(mission)
    db_session.commit()

    admin_client = make_authenticated_client(app, admin)
    response = admin_client.get("/admin/biz/moderation")
    assert response.status_code == 200
    assert b"Moderation queue entry" in response.data


def test_admin_can_approve_pending_offer(
    app: Flask, db_session: Session, emitter: User, admin: User
):
    mission = MissionOffer(
        title="Approvable",
        description="x",
        status=PublicationStatus.PENDING,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
    )
    db_session.add(mission)
    db_session.commit()

    admin_client = make_authenticated_client(app, admin)
    response = admin_client.post(f"/admin/biz/moderation/{mission.id}/approve")
    assert response.status_code == 302
    db_session.refresh(mission)
    assert mission.status == PublicationStatus.PUBLIC


def test_admin_can_reject_pending_offer(
    app: Flask, db_session: Session, emitter: User, admin: User
):
    mission = MissionOffer(
        title="Rejectable",
        description="x",
        status=PublicationStatus.PENDING,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
    )
    db_session.add(mission)
    db_session.commit()

    admin_client = make_authenticated_client(app, admin)
    response = admin_client.post(f"/admin/biz/moderation/{mission.id}/reject")
    assert response.status_code == 302
    db_session.refresh(mission)
    assert mission.status == PublicationStatus.REJECTED


def test_non_admin_cannot_access_moderation(app: Flask, emitter: User):
    client = make_authenticated_client(app, emitter)
    response = client.get("/admin/biz/moderation")
    assert response.status_code in (401, 403)
