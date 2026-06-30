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
from app.services.notifications._models import Notification
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
    emitter: User,
    applicant: User,
):
    client = make_authenticated_client(app, applicant)
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
    # Applying notified the emitter — a cloche row was committed.
    assert db_session.query(Notification).filter_by(receiver_id=emitter.id).count() >= 1


def test_project_decision_buttons_and_badge_on_applications_page(
    app: Flask,
    db_session: Session,
    published_project: ProjectOffer,
    emitter: User,
    applicant: User,
):
    """Bug #0200 (MARKET/PROJECTS) — the emitter accepts/refuses on the
    applications page with BOTH « Accepter » and « Refuser », and the
    status badge reads « Accepté » after a decision. (The status
    comparisons were case-broken — uppercase literal vs lowercase enum
    value — so neither the buttons nor the badge rendered.)"""
    applicant_client = make_authenticated_client(app, applicant)
    applicant_client.post(
        f"/biz/projects/{published_project.id}/apply",
        data={"message": "Je postule"},
    )
    application = (
        db_session.query(OfferApplication)
        .filter_by(offer_id=published_project.id)
        .first()
    )
    emitter_client = make_authenticated_client(app, emitter)

    page = emitter_client.get(f"/biz/projects/{published_project.id}/applications")
    assert page.status_code == 200
    body = page.data.decode()
    assert "Accepter" in body
    assert "Refuser" in body
    assert f"/applications/{application.id}/select" in body
    assert f"/applications/{application.id}/reject" in body

    # Accept it — the badge must then read « Accepté », not « En attente ».
    emitter_client.post(
        f"/biz/projects/{published_project.id}/applications/{application.id}/select",
        data={"decision_message": "Bravo"},
    )
    db_session.refresh(application)
    assert application.status == ApplicationStatus.SELECTED
    after = emitter_client.get(f"/biz/projects/{published_project.id}/applications")
    assert "Accepté" in after.data.decode()


def test_emitter_sees_project_applications(
    app: Flask,
    db_session: Session,
    published_project: ProjectOffer,
    emitter: User,
    applicant: User,
):
    applicant_client = make_authenticated_client(app, applicant)
    applicant_client.post(
        f"/biz/projects/{published_project.id}/apply",
        data={"message": "Motivation pour projet"},
    )
    emitter_client = make_authenticated_client(app, emitter)
    response = emitter_client.get(f"/biz/projects/{published_project.id}/applications")
    assert response.status_code == 200
    assert b"Motivation pour projet" in response.data


def test_project_new_heading_is_generic_not_journalistic(
    app: Flask,
    emitter: User,
):
    """Bug #0206 — the generic publish page must not presume « projet
    journalistique » ; the per-kind labels (communication / innovation /
    journalistique) only appear once a category is picked."""
    client = make_authenticated_client(app, emitter)
    response = client.get("/biz/projects/new")
    assert response.status_code == 200
    body = response.data.decode()
    # Old presumptuous heading gone ; neutral one present.
    assert "Publier un projet journalistique" not in body
    assert "Publier un projet" in body
    # Per-category step labels are rendered (apostrophe-free ones checked
    # to dodge HTML-entity escaping).
    assert "Projet de communication" in body
    assert "Projet journalistique" in body


def test_project_form_offers_category_select_with_fallback(
    app: Flask,
    emitter: User,
):
    """Ticket #0198 — even without ontology data, the publish form
    must render the three categories (journalisme/communication/
    innovation) as the hardcoded fallback."""
    client = make_authenticated_client(app, emitter)
    response = client.get("/biz/projects/new")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Type de projet" in body
    for value in ("journalisme", "communication", "innovation"):
        assert f'value="{value}"' in body, f"project category option {value!r} missing"


def test_project_form_pulls_subtypes_from_ontology(
    app: Flask,
    emitter: User,
):
    """Ticket #0198 — sub-types come from `type_projet_<category>`
    taxonomies (admin-editable)."""
    client = make_authenticated_client(app, emitter)
    with patch(
        "app.modules.biz.views.projects.get_taxonomy",
        side_effect=lambda name: {
            "type_projets": [],
            "type_projet_journalisme": ["Enquête #0198", "Dossier #0198"],
            "type_projet_communication": ["Campagne #0198"],
            "type_projet_innovation": ["Outil IA #0198"],
        }.get(name, []),
    ):
        response = client.get("/biz/projects/new")
    body = response.data.decode()
    for sub in ("Enquête #0198", "Campagne #0198", "Outil IA #0198"):
        assert sub in body, f"sub-type {sub!r} should appear in the form"


def test_project_post_persists_category_and_subtype(
    app: Flask,
    emitter: User,
    db_session: Session,
):
    """A successful POST stores both the top-level category and the
    sub-type on the row."""
    client = make_authenticated_client(app, emitter)
    response = client.post(
        "/biz/projects/new",
        data={
            "title": "Projet test #0198",
            "description": "Description longue pour le projet test #0198.",
            "sector": "tech",
            "project_category": "journalisme",
            "project_type": "Enquête #0198",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    project = (
        db_session.query(ProjectOffer).filter_by(title="Projet test #0198").first()
    )
    assert project is not None
    assert project.project_category == "journalisme"
    assert project.project_type == "Enquête #0198"


def test_project_select_persists_decision_message_and_notifies(
    app: Flask,
    db_session: Session,
    published_project: ProjectOffer,
    emitter: User,
    applicant: User,
):
    """Ticket #0200 — same accept/reject + decision_message flow as
    Missions, applied to Projects."""
    applicant_client = make_authenticated_client(app, applicant)
    applicant_client.post(
        f"/biz/projects/{published_project.id}/apply",
        data={"message": "Je postule au projet."},
    )
    application = (
        db_session.query(OfferApplication)
        .filter_by(offer_id=published_project.id)
        .first()
    )
    assert application is not None

    emitter_client = make_authenticated_client(app, emitter)
    emitter_client.post(
        f"/biz/projects/{published_project.id}/applications/{application.id}/select",
        data={"decision_message": "Vous êtes pris pour le projet."},
        follow_redirects=False,
    )

    db_session.refresh(application)
    assert application.status == ApplicationStatus.SELECTED
    # The decision message is persisted on the application (state, not a mock).
    assert application.decision_message == "Vous êtes pris pour le projet."


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
