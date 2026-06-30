# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end tests for applicant selected/rejected notifications (v0.6)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.biz.models import (
    ApplicationStatus,
    MissionOffer,
    MissionStatus,
    OfferApplication,
)
from app.services.notifications._models import Notification
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"outcome_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def press_role(db_session: Session) -> Role:
    role = Role(
        name=RoleEnum.PRESS_MEDIA.name,
        description=RoleEnum.PRESS_MEDIA.value,
    )
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def scenario(db_session: Session, press_role: Role) -> dict:
    org = Organisation(name="Outcome Test Org")
    db_session.add(org)
    db_session.commit()

    emitter = User(email=_unique_email(), active=True)
    emitter.photo = b""
    emitter.organisation = org
    emitter.organisation_id = org.id
    emitter.roles.append(press_role)
    db_session.add(emitter)

    applicant = User(email=_unique_email(), active=True)
    applicant.photo = b""
    applicant.roles.append(press_role)
    db_session.add(applicant)
    db_session.commit()

    mission = MissionOffer(
        title="Outcome mission",
        description="<p>Outcome test mission description.</p>",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
        emitter_org_id=org.id,
    )
    db_session.add(mission)
    db_session.commit()

    application = OfferApplication(
        offer_id=mission.id,
        owner_id=applicant.id,
        message="Test candidature",
    )
    db_session.add(application)
    db_session.commit()

    return {
        "org": org,
        "emitter": emitter,
        "applicant": applicant,
        "mission": mission,
        "application": application,
    }


def test_selecting_application_notifies_applicant(
    app: Flask, db_session: Session, scenario: dict
):
    applicant_id = scenario["applicant"].id
    emitter_client = make_authenticated_client(app, scenario["emitter"])
    response = emitter_client.post(
        f"/biz/missions/{scenario['mission'].id}"
        f"/applications/{scenario['application'].id}/select"
    )
    assert response.status_code == 302
    db_session.refresh(scenario["application"])
    assert scenario["application"].status == ApplicationStatus.SELECTED
    # The applicant got a committed « sélectionnée » cloche (state, not a mock).
    notifs = db_session.query(Notification).filter_by(receiver_id=applicant_id).all()
    assert any("sélectionnée" in n.message for n in notifs)


def test_rejecting_application_notifies_applicant(
    app: Flask, db_session: Session, scenario: dict
):
    applicant_id = scenario["applicant"].id
    emitter_client = make_authenticated_client(app, scenario["emitter"])
    response = emitter_client.post(
        f"/biz/missions/{scenario['mission'].id}"
        f"/applications/{scenario['application'].id}/reject"
    )
    assert response.status_code == 302
    db_session.refresh(scenario["application"])
    assert scenario["application"].status == ApplicationStatus.REJECTED
    notifs = db_session.query(Notification).filter_by(receiver_id=applicant_id).all()
    assert any("non retenue" in n.message for n in notifs)


def test_resending_same_status_does_not_renotify(
    app: Flask, db_session: Session, scenario: dict
):
    # Pre-mark as SELECTED, then hit select again — should not re-notify.
    scenario["application"].status = ApplicationStatus.SELECTED
    db_session.commit()
    applicant_id = scenario["applicant"].id

    emitter_client = make_authenticated_client(app, scenario["emitter"])
    emitter_client.post(
        f"/biz/missions/{scenario['mission'].id}"
        f"/applications/{scenario['application'].id}/select"
    )
    # No state transition → no new cloche for the applicant.
    assert (
        db_session.query(Notification).filter_by(receiver_id=applicant_id).count() == 0
    )
