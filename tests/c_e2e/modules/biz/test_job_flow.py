# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end workflow tests for Marketplace JobOffer."""

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
    ContractType,
    JobOffer,
    MissionStatus,
    OfferApplication,
)
from app.modules.kyc.ontology_loader import get_ontology_content
from app.services.notifications._models import Notification
from app.services.taxonomies._models import TaxonomyEntry
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


def test_new_form_renders_sector_optgroups(
    app: Flask, emitter: User, db_session: Session
):
    """#0230 — the job deposit form must not crash on the sector field.
    The dual-select ontology is a {"field1", "field2"} dict; feeding the
    whole dict to a flat SelectField made wtforms do `choices[0]` on a
    dict → KeyError. The `field2` sub-dict renders as optgroups instead."""
    db_session.add_all(
        [
            TaxonomyEntry(
                taxonomy_name="secteur_detaille",
                category="ADMINISTRATION PUBLIQUE",
                value="ADMINISTRATION PUBLIQUE / Affaires maritimes",
                name="ADMINISTRATION PUBLIQUE / Affaires maritimes",
                seq=1,
            ),
            TaxonomyEntry(
                taxonomy_name="secteur_detaille",
                category="BTP",
                value="BTP / Génie civil",
                name="BTP / Génie civil",
                seq=2,
            ),
        ]
    )
    db_session.commit()
    get_ontology_content.cache_clear()

    client = make_authenticated_client(app, emitter)
    response = client.get("/biz/jobs/new")

    assert response.status_code == 200
    html = response.data.decode()
    assert '<optgroup label="ADMINISTRATION PUBLIQUE">' in html
    assert "ADMINISTRATION PUBLIQUE / Affaires maritimes" in html


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
    emitter: User,
    applicant: User,
):
    client = make_authenticated_client(app, applicant)
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
    # Applying notified the emitter — a cloche row was committed.
    assert db_session.query(Notification).filter_by(receiver_id=emitter.id).count() >= 1


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
    applicant_client.post(
        f"/biz/jobs/{published_job.id}/apply",
        data={"message": "Trop tard"},
    )
    count = (
        db_session.query(OfferApplication).filter_by(offer_id=published_job.id).count()
    )
    assert count == 0
