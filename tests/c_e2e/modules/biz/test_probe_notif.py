# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Throwaway probe — find a faithful reproduction of the commit-ordering bug."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.biz.models import MissionOffer, MissionStatus
from tests.c_e2e.conftest import make_authenticated_client


def _email():
    return f"probe_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def press_role(db_session):
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(name=RoleEnum.PRESS_MEDIA.name, description="j")
        db_session.add(role)
        db_session.commit()
    return role


def test_probe(app, db_session, press_role):
    org = Organisation(name="Probe Org")
    db_session.add(org)
    db_session.commit()
    emitter = User(email=_email(), active=True, organisation=org, organisation_id=org.id)
    emitter.photo = b""
    emitter.roles.append(press_role)
    applicant = User(email=_email(), active=True)
    applicant.photo = b""
    applicant.roles.append(press_role)
    db_session.add_all([emitter, applicant])
    db_session.commit()
    mission = MissionOffer(
        title="Probe mission",
        description="<p>d</p>",
        sector="media",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
        emitter_org_id=org.id,
    )
    db_session.add(mission)
    db_session.commit()
    emitter_id = emitter.id

    client = make_authenticated_client(app, applicant)
    with patch("app.modules.biz.services.offer_notifications.MissionApplicationMail"):
        client.post(
            f"/biz/missions/{mission.id}/apply", data={"message": "x"}
        )

    # Approach A: raw connection (committed state only)
    with db.engine.connect() as conn:
        raw_count = conn.execute(
            text("SELECT count(*) FROM not_notifications WHERE receiver_id = :r"),
            {"r": emitter_id},
        ).scalar()

    # Approach B: simulate teardown then query via fresh scoped session
    db.session.remove()
    after_remove = (
        db.session.execute(
            text("SELECT count(*) FROM not_notifications WHERE receiver_id = :r"),
            {"r": emitter_id},
        ).scalar()
    )

    print(f"\nPROBE raw_connection_committed_count={raw_count}")
    print(f"PROBE after_session_remove_count={after_remove}")
    # Don't assert — just observe.
