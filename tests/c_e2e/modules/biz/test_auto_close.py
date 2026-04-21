# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end tests for v0.5 — auto-close of expired offers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import (
    JobOffer,
    MissionOffer,
    MissionStatus,
    ProjectOffer,
)
from app.modules.biz.services.auto_close import close_expired_offers

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"autoclose_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def owner(db_session: Session) -> User:
    role = Role(
        name=RoleEnum.PRESS_MEDIA.name,
        description=RoleEnum.PRESS_MEDIA.value,
    )
    db_session.add(role)
    user = User(email=_unique_email(), active=True)
    user.photo = b""
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    return user


def test_close_expired_closes_past_deadlines(
    db_session: Session, owner: User
):
    past = datetime.now(UTC) - timedelta(days=1)
    future = datetime.now(UTC) + timedelta(days=10)

    expired = MissionOffer(
        title="expired mission",
        description="x",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        deadline=past,
        owner_id=owner.id,
    )
    still_open = MissionOffer(
        title="still open mission",
        description="x",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        deadline=future,
        owner_id=owner.id,
    )
    no_deadline = MissionOffer(
        title="no deadline mission",
        description="x",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        owner_id=owner.id,
    )
    expired_project = ProjectOffer(
        title="expired project",
        description="x",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        deadline=past,
        owner_id=owner.id,
    )
    expired_job = JobOffer(
        title="expired job",
        description="x",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        starting_date=past,
        owner_id=owner.id,
    )
    db_session.add_all(
        [expired, still_open, no_deadline, expired_project, expired_job]
    )
    db_session.commit()

    counts = close_expired_offers()
    assert counts == {"missions": 1, "projects": 1, "jobs": 1}

    db_session.expire_all()
    assert (
        db_session.get(MissionOffer, expired.id).mission_status
        == MissionStatus.CLOSED
    )
    assert (
        db_session.get(MissionOffer, still_open.id).mission_status
        == MissionStatus.OPEN
    )
    assert (
        db_session.get(MissionOffer, no_deadline.id).mission_status
        == MissionStatus.OPEN
    )
    assert (
        db_session.get(ProjectOffer, expired_project.id).mission_status
        == MissionStatus.CLOSED
    )
    assert (
        db_session.get(JobOffer, expired_job.id).mission_status
        == MissionStatus.CLOSED
    )


def test_close_expired_skips_already_closed(
    db_session: Session, owner: User
):
    past = datetime.now(UTC) - timedelta(days=1)
    already_filled = MissionOffer(
        title="already filled",
        description="x",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.FILLED,
        deadline=past,
        owner_id=owner.id,
    )
    db_session.add(already_filled)
    db_session.commit()

    counts = close_expired_offers()
    assert counts["missions"] == 0

    db_session.expire_all()
    assert (
        db_session.get(MissionOffer, already_filled.id).mission_status
        == MissionStatus.FILLED
    )
