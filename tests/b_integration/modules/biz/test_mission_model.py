# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Model-level tests for MissionOffer and MissionApplication."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import (
    ApplicationStatus,
    MarketplaceContent,
    MissionApplication,
    MissionOffer,
    MissionStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.auth import User
    from app.models.organisation import Organisation


def _make_mission(
    db_session: Session,
    test_emitter: User,
    test_org: Organisation,
    **overrides,
) -> MissionOffer:
    defaults = {
        "title": "Rédiger 3 articles sur l'IA",
        "description": "<p>Contexte & contraintes</p>",
        "sector": "tech",
        "location": "Paris",
        "status": PublicationStatus.PUBLIC,
        "owner_id": test_emitter.id,
        "emitter_org_id": test_org.id,
    }
    defaults.update(overrides)
    mission = MissionOffer(**defaults)
    db_session.add(mission)
    db_session.flush()
    return mission


def test_mission_offer_polymorphic_identity(
    db_session: Session, test_emitter, test_org
):
    mission = _make_mission(db_session, test_emitter, test_org)
    fetched = db_session.get(MarketplaceContent, mission.id)
    assert fetched is not None
    assert fetched.type == "mission_offer"
    assert isinstance(fetched, MissionOffer)


def test_mission_offer_defaults(
    db_session: Session, test_emitter, test_org
):
    mission = _make_mission(db_session, test_emitter, test_org)
    assert mission.mission_status == MissionStatus.OPEN
    assert mission.currency == "EUR"
    assert mission.budget_min is None
    assert mission.budget_max is None


def test_application_unique_per_user(
    db_session: Session, test_emitter, test_org, test_applicant
):
    mission = _make_mission(db_session, test_emitter, test_org)

    first = MissionApplication(
        mission_id=mission.id,
        owner_id=test_applicant.id,
        message="Je suis intéressé",
    )
    db_session.add(first)
    db_session.flush()
    assert first.status == ApplicationStatus.PENDING

    second = MissionApplication(
        mission_id=mission.id,
        owner_id=test_applicant.id,
        message="Relance",
    )
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_application_cascade_delete(
    db_session: Session, test_emitter, test_org, test_applicant
):
    mission = _make_mission(db_session, test_emitter, test_org)
    app = MissionApplication(
        mission_id=mission.id,
        owner_id=test_applicant.id,
    )
    db_session.add(app)
    db_session.flush()

    app_id = app.id
    db_session.delete(mission)
    db_session.flush()

    assert db_session.get(MissionApplication, app_id) is None
