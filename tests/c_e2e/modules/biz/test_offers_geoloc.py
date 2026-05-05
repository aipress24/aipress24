# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for #0021 phase 5 — geoloc on biz offers.

Verifies that an offer carrying structured `pays_zip_ville` /
`pays_zip_ville_detail` renders its location through the
`offer_geoloc` filter on the detail page (and falls back to the
legacy `location` field for older records).
"""

from __future__ import annotations

import uuid
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
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"geo_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def _press_role(db_session: Session) -> Role:
    role = Role(
        name=RoleEnum.PRESS_MEDIA.name,
        description=RoleEnum.PRESS_MEDIA.value,
    )
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def emitter(db_session: Session, _press_role: Role) -> User:
    user = User(email=_unique_email(), first_name="Geo", last_name="Emit", active=True)
    user.photo = b""
    user.roles.append(_press_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def client(app: Flask, emitter: User) -> FlaskClient:
    return make_authenticated_client(app, emitter)


class TestMissionGeoloc:
    def test_detail_uses_structured_geoloc(
        self, db_session: Session, client: FlaskClient, emitter: User
    ) -> None:
        mission = MissionOffer(
            title="Mission FR",
            description="x" * 50,
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=emitter.id,
            pays_zip_ville="FRA",
            pays_zip_ville_detail="FRA / 75001 Paris",
        )
        db_session.add(mission)
        db_session.commit()

        response = client.get(f"/biz/missions/{mission.id}")

        assert response.status_code == 200
        assert b"Localisation" in response.data

    def test_detail_falls_back_to_legacy_location(
        self, db_session: Session, client: FlaskClient, emitter: User
    ) -> None:
        mission = MissionOffer(
            title="Mission legacy",
            description="x" * 50,
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=emitter.id,
            location="Brest",
        )
        db_session.add(mission)
        db_session.commit()

        response = client.get(f"/biz/missions/{mission.id}")

        assert response.status_code == 200
        assert b"Brest" in response.data

    def test_detail_omits_section_when_unset(
        self, db_session: Session, client: FlaskClient, emitter: User
    ) -> None:
        mission = MissionOffer(
            title="Mission without location",
            description="x" * 50,
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=emitter.id,
        )
        db_session.add(mission)
        db_session.commit()

        response = client.get(f"/biz/missions/{mission.id}")

        assert response.status_code == 200
        # The "Localisation" <dt> is conditional ; should not appear when
        # neither structured nor legacy fields are filled.
        assert b"Localisation" not in response.data


class TestProjectGeoloc:
    def test_detail_uses_structured_geoloc(
        self, db_session: Session, client: FlaskClient, emitter: User
    ) -> None:
        project = ProjectOffer(
            title="Project FR",
            description="x" * 50,
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=emitter.id,
            pays_zip_ville="FRA",
            pays_zip_ville_detail="FRA / 69001 Lyon",
        )
        db_session.add(project)
        db_session.commit()

        response = client.get(f"/biz/projects/{project.id}")

        assert response.status_code == 200
        assert b"Localisation" in response.data


class TestJobGeoloc:
    def test_detail_uses_structured_geoloc(
        self, db_session: Session, client: FlaskClient, emitter: User
    ) -> None:
        job = JobOffer(
            title="Job FR",
            description="x" * 50,
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=emitter.id,
            pays_zip_ville="FRA",
            pays_zip_ville_detail="FRA / 13001 Marseille",
        )
        db_session.add(job)
        db_session.commit()

        response = client.get(f"/biz/jobs/{job.id}")

        assert response.status_code == 200
        assert b"Lieu" in response.data
