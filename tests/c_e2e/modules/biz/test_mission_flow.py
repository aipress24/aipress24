# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end workflow tests for Marketplace Missions MVP."""

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
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"mission_{uuid.uuid4().hex[:8]}@example.com"


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
    org = Organisation(name="Mission Test Org")
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
def published_mission(
    db_session: Session, emitter: User, org: Organisation
) -> MissionOffer:
    mission = MissionOffer(
        title="Pige test — rédaction IA",
        description="<p>Description de la mission test.</p>",
        sector="tech",
        location="Paris",
        status=PublicationStatus.PUBLIC,
        mission_status=MissionStatus.OPEN,
        owner_id=emitter.id,
        emitter_org_id=org.id,
    )
    db_session.add(mission)
    db_session.commit()
    return mission


class TestMissionsListing:
    def test_missions_tab_lists_public_missions(
        self,
        app: Flask,
        emitter: User,
        published_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, emitter)
        response = client.get("/biz/?current_tab=missions")
        assert response.status_code == 200
        assert b"Pige test" in response.data

    def test_anonymous_redirected_from_missions(self, client: FlaskClient):
        response = client.get("/biz/?current_tab=missions")
        assert response.status_code in (302, 401)


class TestMissionDeposit:
    def test_emitter_can_post_mission(
        self,
        app: Flask,
        emitter: User,
        db_session: Session,
    ):
        client = make_authenticated_client(app, emitter)
        response = client.post(
            "/biz/missions/new",
            data={
                "title": "Nouvelle mission test",
                "description": ("Une description suffisamment longue pour le test."),
                "sector": "media",
                "location": "Lyon",
                "budget_min": "500",
                "budget_max": "1500",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        mission = (
            db_session.query(MissionOffer)
            .filter_by(title="Nouvelle mission test")
            .first()
        )
        assert mission is not None
        assert mission.owner_id == emitter.id
        assert mission.budget_min == 50_000
        assert mission.budget_max == 150_000
        assert mission.mission_status == MissionStatus.OPEN
        assert mission.status == PublicationStatus.PUBLIC


class TestOfferApplication:
    def test_applicant_can_apply(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        applicant: User,
    ):
        client = make_authenticated_client(app, applicant)
        with patch(
            "app.modules.biz.views._offers_common.notify_emitter_of_application"
        ) as mock_notify:
            response = client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Je suis intéressé par cette pige."},
                follow_redirects=False,
            )

        assert response.status_code == 302
        application = (
            db_session.query(OfferApplication)
            .filter_by(
                offer_id=published_mission.id,
                owner_id=applicant.id,
            )
            .first()
        )
        assert application is not None
        assert application.status == ApplicationStatus.PENDING
        mock_notify.assert_called_once()

    def test_emitter_cannot_apply_to_own_mission(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        emitter: User,
    ):
        client = make_authenticated_client(app, emitter)
        client.post(
            f"/biz/missions/{published_mission.id}/apply",
            data={"message": "Test"},
            follow_redirects=False,
        )
        count = (
            db_session.query(OfferApplication)
            .filter_by(offer_id=published_mission.id)
            .count()
        )
        assert count == 0

    def test_double_application_rejected(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        applicant: User,
    ):
        client = make_authenticated_client(app, applicant)
        with patch(
            "app.modules.biz.views._offers_common.notify_emitter_of_application"
        ):
            client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Première"},
            )
            client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Deuxième"},
            )
        count = (
            db_session.query(OfferApplication)
            .filter_by(
                offer_id=published_mission.id,
                owner_id=applicant.id,
            )
            .count()
        )
        assert count == 1


class TestMissionDashboard:
    def test_emitter_sees_applications_list(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        emitter: User,
        applicant: User,
    ):
        applicant_client = make_authenticated_client(app, applicant)
        with patch(
            "app.modules.biz.views._offers_common.notify_emitter_of_application"
        ):
            applicant_client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Ma candidature"},
            )

        emitter_client = make_authenticated_client(app, emitter)
        response = emitter_client.get(
            f"/biz/missions/{published_mission.id}/applications"
        )
        assert response.status_code == 200
        assert b"Ma candidature" in response.data

    def test_emitter_can_select_application(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        emitter: User,
        applicant: User,
    ):
        applicant_client = make_authenticated_client(app, applicant)
        with patch(
            "app.modules.biz.views._offers_common.notify_emitter_of_application"
        ):
            applicant_client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Test"},
            )
        application = (
            db_session.query(OfferApplication)
            .filter_by(offer_id=published_mission.id)
            .first()
        )
        assert application is not None

        emitter_client = make_authenticated_client(app, emitter)
        response = emitter_client.post(
            f"/biz/missions/{published_mission.id}"
            f"/applications/{application.id}/select",
            follow_redirects=False,
        )
        assert response.status_code == 302
        db_session.refresh(application)
        assert application.status == ApplicationStatus.SELECTED

    def test_mission_fill_blocks_new_applications(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        emitter: User,
        applicant: User,
    ):
        emitter_client = make_authenticated_client(app, emitter)
        emitter_client.post(f"/biz/missions/{published_mission.id}/fill")
        db_session.refresh(published_mission)
        assert published_mission.mission_status == MissionStatus.FILLED

        applicant_client = make_authenticated_client(app, applicant)
        with patch(
            "app.modules.biz.views._offers_common.notify_emitter_of_application"
        ):
            applicant_client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Trop tard"},
            )

        count = (
            db_session.query(OfferApplication)
            .filter_by(offer_id=published_mission.id)
            .count()
        )
        assert count == 0

    def test_non_owner_cannot_see_applications(
        self,
        app: Flask,
        published_mission: MissionOffer,
        applicant: User,
    ):
        applicant_client = make_authenticated_client(app, applicant)
        response = applicant_client.get(
            f"/biz/missions/{published_mission.id}/applications"
        )
        assert response.status_code == 403


class TestOpenMissionShowsApplyForm:
    """Ticket #0161: a freshly published (OPEN) mission must let other
    users apply. `MissionStatus(StrEnum)` + `auto()` makes `.value`
    lowercase ("open"), but the detail templates used to compare it to
    "OPEN" — so the apply branch was never reachable and every OPEN
    mission wrongly showed "n'accepte plus de candidatures" (same
    enum-name-mismatch class as #0150 / lessons-learned #11).
    """

    def test_open_mission_renders_apply_form_for_other_user(
        self,
        app: Flask,
        applicant: User,
        published_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, applicant)
        response = client.get(f"/biz/missions/{published_mission.id}")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Candidater" in body
        assert f"/biz/missions/{published_mission.id}/apply" in body
        assert "n'accepte plus de candidatures" not in body


class TestPosterCardOnMissionAd:
    """Bug #0183 (Erick, 2026-06-04) — MARKET/MISSIONS : « Le problème,
    c'est qu'on ne voit pas qui l'a postée. → Suggestion : mettre la
    mini carte du profil de la personne qui poste [...] en
    accompagnement de l'annonce lorsqu'elle est affichée sur le
    portail d'annonces. »
    """

    def _named_emitter(self, db_session: Session, org: Organisation, press_role: Role):
        user = User(
            email=_unique_email(),
            first_name="Nicolas",
            last_name="Mouriou",
            active=True,
        )
        user.photo = b""
        user.organisation = org
        user.organisation_id = org.id
        user.roles.append(press_role)
        db_session.add(user)
        db_session.flush()
        return user

    def _open_mission(
        self, db_session: Session, owner: User, org: Organisation
    ) -> MissionOffer:
        mission = MissionOffer(
            title="Mission pour test #0183",
            description="<p>Recherche pigiste sur sujet IA.</p>",
            sector="tech",
            location="Paris",
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=owner.id,
            emitter_org_id=org.id,
        )
        db_session.add(mission)
        db_session.commit()
        return mission

    def test_poster_appears_on_missions_listing(
        self,
        app: Flask,
        db_session: Session,
        press_role: Role,
        org: Organisation,
    ):
        owner = self._named_emitter(db_session, org, press_role)
        self._open_mission(db_session, owner, org)

        client = make_authenticated_client(app, owner)
        response = client.get("/biz/?current_tab=missions")
        assert response.status_code == 200
        body = response.data.decode()

        assert "Nicolas Mouriou" in body, (
            "the mission listing must show the poster's full name "
            "next to / under the mission card (#0183)"
        )

    def test_poster_appears_on_mission_detail_with_profile_link(
        self,
        app: Flask,
        db_session: Session,
        press_role: Role,
        org: Organisation,
        applicant: User,
    ):
        owner = self._named_emitter(db_session, org, press_role)
        mission = self._open_mission(db_session, owner, org)

        # View as a different user so the page doesn't render the
        # owner-view edit affordances and we focus on the public
        # poster surface.
        viewer_client = make_authenticated_client(app, applicant)
        response = viewer_client.get(f"/biz/missions/{mission.id}")
        assert response.status_code == 200
        body = response.data.decode()

        assert "Nicolas Mouriou" in body, "mission detail must show the poster name"
        assert f"/swork/members/{owner.id}" in body, (
            "mission detail must link to the poster's profile"
        )


class TestApplicantCardsOnApplicationsPage:
    """Bug #0184 (Erick, 2026-06-04) — MARKET/MISSIONS : « Certes on
    voit leur nom mais ce n'est pas très parlant car il n'y a aucun
    lien. → Suggestion : mettre la mini carte des répondants un peu
    comme dans NEWS avec lien vers le profil et lien vers le BW [...]
    SANS la phrase "Publié par X en tant que contact presse de Y"
    qui, ici, ne sert à rien. »
    """

    def test_applicants_render_with_profile_link(
        self,
        app: Flask,
        db_session: Session,
        emitter: User,
        published_mission: MissionOffer,
        press_role: Role,
    ):
        # Two distinct applicants with full names.
        a1 = User(
            email=_unique_email(),
            first_name="Aïcha",
            last_name="BenMahfoud",
            active=True,
        )
        a2 = User(
            email=_unique_email(),
            first_name="Annick",
            last_name="Stramazian",
            active=True,
        )
        for u in (a1, a2):
            u.photo = b""
            u.roles.append(press_role)
        db_session.add_all([a1, a2])
        db_session.commit()

        for a in (a1, a2):
            client = make_authenticated_client(app, a)
            with patch(
                "app.modules.biz.views._offers_common.notify_emitter_of_application"
            ):
                client.post(
                    f"/biz/missions/{published_mission.id}/apply",
                    data={"message": f"Candidature de {a.first_name}."},
                )

        emitter_client = make_authenticated_client(app, emitter)
        response = emitter_client.get(
            f"/biz/missions/{published_mission.id}/applications"
        )
        assert response.status_code == 200
        body = response.data.decode()

        for applicant_user in (a1, a2):
            assert applicant_user.full_name in body, (
                f"applicant {applicant_user.full_name} name missing"
            )
            assert f"/swork/members/{applicant_user.id}" in body, (
                f"profile link for {applicant_user.full_name} missing (#0184)"
            )

        # Erick : SANS la phrase "Publié par X en tant que contact
        # presse de Y" qui, ici, ne sert à rien.
        assert "en tant que contact presse de" not in body, (
            "the Wire-style press-relations attribution line is "
            "irrelevant on the marketplace applications page (#0184)"
        )
