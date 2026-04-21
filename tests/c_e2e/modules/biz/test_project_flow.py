# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end workflow tests for Marketplace ProjectOffer."""

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
    MissionStatus,
    OfferApplication,
    ProjectOffer,
)
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"project_{uuid.uuid4().hex[:8]}@example.com"


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
def org(db_session: Session) -> Organisation:
    org = Organisation(name="Project Test Org")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def emitter(db_session: Session, org: Organisation, press_role: Role) -> User:
    user = User(email=_unique_email(), active=True)
    user.photo = b""
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(press_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def applicant(db_session: Session, press_role: Role) -> User:
    user = User(email=_unique_email(), active=True)
    user.photo = b""
    user.roles.append(press_role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def published_project(
    db_session: Session, emitter: User, org: Organisation
) -> ProjectOffer:
    project = ProjectOffer(
        title="Enquête collaborative — climat",
        description="<p>Projet d'enquête sur 4 mois, équipe de 3.</p>",
        sector="climat",
        location="France",
        team_size=3,
        duration_months=4,
        project_type="enquête",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
        emitter_org_id=org.id,
    )
    db_session.add(project)
    db_session.commit()
    return project


def test_projects_tab_lists_public_projects(
    app: Flask, emitter: User, published_project: ProjectOffer
):
    client = make_authenticated_client(app, emitter)
    response = client.get("/biz/?current_tab=projects")
    assert response.status_code == 200
    assert b"Enqu" in response.data  # "Enquête" sans accents problèmes


def test_emitter_can_post_project(app: Flask, emitter: User, db_session: Session):
    client = make_authenticated_client(app, emitter)
    response = client.post(
        "/biz/projects/new",
        data={
            "title": "Nouveau projet test",
            "description": "Description suffisamment longue du projet.",
            "sector": "culture",
            "location": "Lyon",
            "team_size": "2",
            "duration_months": "3",
            "project_type": "série",
            "budget_min": "2000",
            "budget_max": "5000",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    project = (
        db_session.query(ProjectOffer).filter_by(title="Nouveau projet test").first()
    )
    assert project is not None
    assert project.team_size == 2
    assert project.duration_months == 3
    assert project.project_type == "série"
    assert project.budget_min == 200_000
    assert project.budget_max == 500_000


def test_applicant_can_apply_to_project(
    app: Flask,
    db_session: Session,
    published_project: ProjectOffer,
    applicant: User,
):
    client = make_authenticated_client(app, applicant)
    with patch(
        "app.modules.biz.views._offers_common.notify_emitter_of_application"
    ) as mock_notify:
        response = client.post(
            f"/biz/projects/{published_project.id}/apply",
            data={"message": "Intéressé par cette enquête."},
            follow_redirects=False,
        )
    assert response.status_code == 302
    application = (
        db_session.query(OfferApplication)
        .filter_by(offer_id=published_project.id, owner_id=applicant.id)
        .first()
    )
    assert application is not None
    assert application.status == ApplicationStatus.PENDING
    mock_notify.assert_called_once()


def test_emitter_sees_project_applications(
    app: Flask,
    db_session: Session,
    published_project: ProjectOffer,
    emitter: User,
    applicant: User,
):
    applicant_client = make_authenticated_client(app, applicant)
    with patch("app.modules.biz.views._offers_common.notify_emitter_of_application"):
        applicant_client.post(
            f"/biz/projects/{published_project.id}/apply",
            data={"message": "Motivation pour projet"},
        )
    emitter_client = make_authenticated_client(app, emitter)
    response = emitter_client.get(f"/biz/projects/{published_project.id}/applications")
    assert response.status_code == 200
    assert b"Motivation pour projet" in response.data


def test_project_fill_blocks_new_applications(
    app: Flask,
    db_session: Session,
    published_project: ProjectOffer,
    emitter: User,
    applicant: User,
):
    emitter_client = make_authenticated_client(app, emitter)
    emitter_client.post(f"/biz/projects/{published_project.id}/fill")
    db_session.refresh(published_project)
    assert published_project.mission_status == MissionStatus.FILLED

    applicant_client = make_authenticated_client(app, applicant)
    with patch("app.modules.biz.views._offers_common.notify_emitter_of_application"):
        applicant_client.post(
            f"/biz/projects/{published_project.id}/apply",
            data={"message": "Trop tard"},
        )
    count = (
        db_session.query(OfferApplication)
        .filter_by(offer_id=published_project.id)
        .count()
    )
    assert count == 0
