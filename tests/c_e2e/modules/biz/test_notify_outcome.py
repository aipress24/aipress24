# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end tests for applicant selected/rejected notifications (v0.6)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

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


def test_selecting_application_emails_applicant(
    app: Flask, db_session: Session, scenario: dict
):
    emitter_client = make_authenticated_client(app, scenario["emitter"])
    with patch(
        "app.modules.biz.views._offers_common.notify_applicant_selected"
    ) as mock_selected:
        response = emitter_client.post(
            f"/biz/missions/{scenario['mission'].id}"
            f"/applications/{scenario['application'].id}/select"
        )
    assert response.status_code == 302
    mock_selected.assert_called_once()
    db_session.refresh(scenario["application"])
    assert scenario["application"].status == ApplicationStatus.SELECTED


def test_rejecting_application_emails_applicant(
    app: Flask, db_session: Session, scenario: dict
):
    emitter_client = make_authenticated_client(app, scenario["emitter"])
    with patch(
        "app.modules.biz.views._offers_common.notify_applicant_rejected"
    ) as mock_rejected:
        response = emitter_client.post(
            f"/biz/missions/{scenario['mission'].id}"
            f"/applications/{scenario['application'].id}/reject"
        )
    assert response.status_code == 302
    mock_rejected.assert_called_once()
    db_session.refresh(scenario["application"])
    assert scenario["application"].status == ApplicationStatus.REJECTED


def test_resending_same_status_does_not_reemail(
    app: Flask, db_session: Session, scenario: dict
):
    # Pre-mark as SELECTED, then hit select again — should not re-email.
    scenario["application"].status = ApplicationStatus.SELECTED
    db_session.commit()

    emitter_client = make_authenticated_client(app, scenario["emitter"])
    with patch(
        "app.modules.biz.views._offers_common.notify_applicant_selected"
    ) as mock_selected:
        emitter_client.post(
            f"/biz/missions/{scenario['mission'].id}"
            f"/applications/{scenario['application'].id}/select"
        )
    mock_selected.assert_not_called()
