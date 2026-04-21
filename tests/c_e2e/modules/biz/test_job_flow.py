# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end workflow tests for Marketplace JobOffer."""

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
    ContractType,
    JobOffer,
    MissionStatus,
    OfferApplication,
)
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"job_{uuid.uuid4().hex[:8]}@example.com"


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
    org = Organisation(name="Job Test Org")
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
def published_job(db_session: Session, emitter: User, org: Organisation) -> JobOffer:
    job = JobOffer(
        title="Journaliste web — CDI",
        description="<p>Poste de journaliste web en CDI, plein temps.</p>",
        sector="media",
        location="Paris",
        contract_type=ContractType.CDI,
        full_time=True,
        remote_ok=True,
        salary_min=3_500_000,  # 35k€/an in cents
        salary_max=4_500_000,
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
        emitter_org_id=org.id,
    )
    db_session.add(job)
    db_session.commit()
    return job


def test_jobs_tab_lists_public_jobs(app: Flask, emitter: User, published_job: JobOffer):
    client = make_authenticated_client(app, emitter)
    response = client.get("/biz/?current_tab=jobs")
    assert response.status_code == 200
    assert b"Journaliste web" in response.data


def test_emitter_can_post_job(app: Flask, emitter: User, db_session: Session):
    client = make_authenticated_client(app, emitter)
    response = client.post(
        "/biz/jobs/new",
        data={
            "title": "Reporter — CDD 6 mois",
            "description": "Description suffisamment longue de l'offre.",
            "sector": "media",
            "location": "Marseille",
            "contract_type": "CDD",
            "full_time": "y",
            "salary_min": "28000",
            "salary_max": "32000",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    job = db_session.query(JobOffer).filter_by(title="Reporter — CDD 6 mois").first()
    assert job is not None
    assert job.contract_type == ContractType.CDD
    assert job.full_time is True
    assert job.remote_ok is False  # not checked
    assert job.salary_min == 2_800_000  # cents
    assert job.salary_max == 3_200_000


def test_applicant_can_apply_to_job_with_cv_url(
    app: Flask,
    db_session: Session,
    published_job: JobOffer,
    applicant: User,
):
    client = make_authenticated_client(app, applicant)
    with patch(
        "app.modules.biz.views._offers_common.notify_emitter_of_application"
    ) as mock_notify:
        response = client.post(
            f"/biz/jobs/{published_job.id}/apply",
            data={
                "message": "Intéressé par le poste.",
                "cv_url": "https://example.com/cv.pdf",
            },
            follow_redirects=False,
        )
    assert response.status_code == 302
    application = (
        db_session.query(OfferApplication)
        .filter_by(offer_id=published_job.id, owner_id=applicant.id)
        .first()
    )
    assert application is not None
    assert application.cv_url == "https://example.com/cv.pdf"
    assert application.status == ApplicationStatus.PENDING
    mock_notify.assert_called_once()


def test_job_fill_blocks_new_applications(
    app: Flask,
    db_session: Session,
    published_job: JobOffer,
    emitter: User,
    applicant: User,
):
    emitter_client = make_authenticated_client(app, emitter)
    emitter_client.post(f"/biz/jobs/{published_job.id}/fill")
    db_session.refresh(published_job)
    assert published_job.mission_status == MissionStatus.FILLED

    applicant_client = make_authenticated_client(app, applicant)
    with patch("app.modules.biz.views._offers_common.notify_emitter_of_application"):
        applicant_client.post(
            f"/biz/jobs/{published_job.id}/apply",
            data={"message": "Trop tard"},
        )
    count = (
        db_session.query(OfferApplication).filter_by(offer_id=published_job.id).count()
    )
    assert count == 0
