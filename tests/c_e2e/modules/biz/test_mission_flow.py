# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end workflow tests for Marketplace Missions MVP."""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.biz.models import (
    ApplicationStatus,
    MissionCategory,
    MissionOffer,
    MissionStatus,
    OfferApplication,
)
from app.services.notifications import NotificationService
from app.services.notifications._models import Notification
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
                # #0224 — category is now required on the form.
                "category": "communication",
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

    def test_application_posts_bell_to_emitter(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        emitter: User,
        applicant: User,
    ):
        """Bug #0200 — a new candidacy must alert the emitter on the bell
        (cloche), not only by e-mail."""
        client = make_authenticated_client(app, applicant)
        # Isolate the e-mail side so only the cloche is under test.
        with patch(
            "app.modules.biz.services.offer_notifications.MissionApplicationMail"
        ) as mail_cls:
            mail_cls.return_value.send.return_value = None
            response = client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Je postule"},
                follow_redirects=False,
            )

        assert response.status_code == 302
        notifs = container.get(NotificationService).get_notifications(emitter)
        assert any(
            applicant.full_name in n.message and published_mission.title in n.message
            for n in notifs
        ), "emitter must receive an in-app cloche for the new application (#0200)"

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


class TestNotificationClochePersistsAcrossTeardown:
    """Bug #0200 (Erick 2026-06-29) — « reçoit le mail mais pas la cloche ».

    `NotificationService.post()` only does `repo.add()` (no commit). The
    decision/application routes commit their state change BEFORE calling
    the notify helper, then redirect with no second commit — so at request
    teardown (`session.remove()`) the freshly-added Notification row is
    rolled back. The mail (immediate I/O) goes out, the bell never
    persists.

    These tests reproduce production by simulating teardown with
    `db.session.remove()` and then querying COMMITTED state. The existing
    bell tests miss the bug because they read the still-open request
    session, which holds the (uncommitted) row.
    """

    def test_emitter_cloche_persists_after_teardown(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        emitter: User,
        applicant: User,
    ):
        emitter_id = emitter.id
        client = make_authenticated_client(app, applicant)
        with patch(
            "app.modules.biz.services.offer_notifications.MissionApplicationMail"
        ):
            resp = client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Je postule"},
            )
        assert resp.status_code == 302

        db.session.remove()  # simulate request teardown
        notifs = (
            db.session.query(Notification).filter_by(receiver_id=emitter_id).all()
        )
        assert notifs, "emitter new-application cloche was rolled back (#0200)"

    def test_applicant_decision_cloche_persists_after_teardown(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        emitter: User,
        applicant: User,
    ):
        applicant_id = applicant.id
        applicant_client = make_authenticated_client(app, applicant)
        with patch(
            "app.modules.biz.views._offers_common.notify_emitter_of_application"
        ):
            applicant_client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Je postule"},
            )
        application = (
            db_session.query(OfferApplication)
            .filter_by(offer_id=published_mission.id, owner_id=applicant_id)
            .one()
        )
        app_id = application.id

        emitter_client = make_authenticated_client(app, emitter)
        with patch(
            "app.modules.biz.services.offer_notifications.ApplicationSelectedMail"
        ):
            resp = emitter_client.post(
                f"/biz/missions/{published_mission.id}"
                f"/applications/{app_id}/select",
                data={"decision_message": "Bravo"},
            )
        assert resp.status_code == 302

        db.session.remove()  # simulate request teardown
        notifs = (
            db.session.query(Notification).filter_by(receiver_id=applicant_id).all()
        )
        assert any("sélectionnée" in n.message for n in notifs), (
            "applicant accept/reject cloche was rolled back (#0200)"
        )


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

    def test_decision_buttons_are_on_the_applications_page_not_the_detail(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        emitter: User,
        applicant: User,
    ):
        """Bug #0200 — the emitter accepts/refuses a candidacy ON the
        applications page (« page où la candidate donne sa réponse »),
        with BOTH « Accepter » and « Refuser » present ; the detail page
        carries no decision buttons."""
        applicant_client = make_authenticated_client(app, applicant)
        with patch(
            "app.modules.biz.views._offers_common.notify_emitter_of_application"
        ):
            applicant_client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Je postule"},
            )
        application = (
            db_session.query(OfferApplication)
            .filter_by(offer_id=published_mission.id)
            .first()
        )
        emitter_client = make_authenticated_client(app, emitter)

        # Applications page: both buttons + their endpoints.
        apps = emitter_client.get(f"/biz/missions/{published_mission.id}/applications")
        assert apps.status_code == 200
        apps_body = apps.data.decode()
        assert "Accepter" in apps_body
        assert "Refuser" in apps_body
        assert f"/applications/{application.id}/select" in apps_body
        assert f"/applications/{application.id}/reject" in apps_body

        # Detail page: no decision buttons (they belong on /applications).
        detail = emitter_client.get(f"/biz/missions/{published_mission.id}")
        assert detail.status_code == 200
        detail_body = detail.data.decode()
        assert f"/applications/{application.id}/select" not in detail_body
        assert f"/applications/{application.id}/reject" not in detail_body

    def test_select_persists_decision_message_and_notifies(
        self,
        app: Flask,
        db_session: Session,
        published_mission: MissionOffer,
        emitter: User,
        applicant: User,
    ):
        """Tickets #0199 + #0200 — the emitter can attach a free-text
        message to the accept/reject decision. Persisted on the
        application row, e-mailed to the candidate via
        ApplicationSelectedMail.decision_message, AND posted as an
        in-app cloche."""
        # Submit application.
        applicant_client = make_authenticated_client(app, applicant)
        with patch(
            "app.modules.biz.views._offers_common.notify_emitter_of_application"
        ):
            applicant_client.post(
                f"/biz/missions/{published_mission.id}/apply",
                data={"message": "Je postule"},
            )
        application = (
            db_session.query(OfferApplication)
            .filter_by(offer_id=published_mission.id)
            .first()
        )
        assert application is not None

        # Emitter selects with a custom message.
        emitter_client = make_authenticated_client(app, emitter)
        with patch(
            "app.modules.biz.services.offer_notifications.ApplicationSelectedMail"
        ) as mail_cls:
            mail_cls.return_value.send.return_value = None
            response = emitter_client.post(
                f"/biz/missions/{published_mission.id}"
                f"/applications/{application.id}/select",
                data={"decision_message": "Bravo, vous êtes pris."},
                follow_redirects=False,
            )

        assert response.status_code == 302
        db_session.refresh(application)
        assert application.status == ApplicationStatus.SELECTED
        assert application.decision_message == "Bravo, vous êtes pris."

        # The mailer received the message.
        assert mail_cls.called
        assert mail_cls.call_args.kwargs["decision_message"] == (
            "Bravo, vous êtes pris."
        )

        # And the in-app cloche fired for the applicant.
        notifs = container.get(NotificationService).get_notifications(applicant)
        assert any(
            published_mission.title in n.message
            and "Bravo, vous êtes pris." in n.message
            for n in notifs
        )

    def test_reject_persists_decision_message_and_notifies(
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
                data={"message": "Je postule"},
            )
        application = (
            db_session.query(OfferApplication)
            .filter_by(offer_id=published_mission.id)
            .first()
        )
        assert application is not None

        emitter_client = make_authenticated_client(app, emitter)
        with patch(
            "app.modules.biz.services.offer_notifications.ApplicationRejectedMail"
        ) as mail_cls:
            mail_cls.return_value.send.return_value = None
            emitter_client.post(
                f"/biz/missions/{published_mission.id}"
                f"/applications/{application.id}/reject",
                data={"decision_message": "Désolé, profil non retenu."},
                follow_redirects=False,
            )

        db_session.refresh(application)
        assert application.status == ApplicationStatus.REJECTED
        assert application.decision_message == "Désolé, profil non retenu."
        assert mail_cls.called
        assert mail_cls.call_args.kwargs["decision_message"] == (
            "Désolé, profil non retenu."
        )

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


class TestMissionCategorySubtyping:
    """Bug #0185 (Erick, 2026-06-04) : MARKET/MISSIONS — sub-type the
    missions in 3 categories with their own sub-taxonomies :

    > 1- Pour le journalisme (annonces visibles seulement par les
    >    journalistes)
    > 2- Pour la Communication (les PR Agencies et les PR Indeps)
    > 3- Pour l'innovation dans le journalisme et la communication.

    v0 hardcodes a small placeholder sub-list per category — the
    full ontology seed is on Erick's side and will land in a later
    commit (#0185 follow-up). The DB shape and the form contract
    are wired so the swap is one-line later.
    """

    def test_form_persists_category_and_subcategory(
        self,
        app: Flask,
        emitter: User,
        db_session: Session,
    ):
        client = make_authenticated_client(app, emitter)
        response = client.post(
            "/biz/missions/new",
            data={
                "title": "Cherche pigiste IA",
                "description": "Une description suffisamment longue pour le test.",
                "sector": "media",
                "category": "journalisme",
                "subcategory": "Enquête",
                "budget_min": "500",
                "budget_max": "1500",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302, response.data[:500]

        mission = (
            db_session.query(MissionOffer).filter_by(title="Cherche pigiste IA").first()
        )
        assert mission is not None
        assert mission.category is not None, (
            "MissionOffer.category must be persisted from the form (#0185)"
        )
        assert mission.category.value == "journalisme"
        assert mission.subcategory == "Enquête"

    def test_missing_category_is_rejected(
        self,
        app: Flask,
        emitter: User,
        db_session: Session,
    ):
        """Bug #0224 — category is required : a mission posted without one
        must NOT be created (otherwise it'd be NULL and, if journalism,
        leak past the Press & Media gate). The form re-renders (200)
        rather than redirecting (302)."""
        client = make_authenticated_client(app, emitter)
        response = client.post(
            "/biz/missions/new",
            data={
                "title": "Mission sans catégorie",
                "description": "Une description suffisamment longue pour le test.",
                "sector": "media",
                "budget_min": "500",
                "budget_max": "1500",
            },
            follow_redirects=False,
        )
        # Validation failure re-renders the form (200), no redirect.
        assert response.status_code == 200

        mission = (
            db_session.query(MissionOffer)
            .filter_by(title="Mission sans catégorie")
            .first()
        )
        assert mission is None

    def test_new_form_template_offers_three_categories(
        self,
        app: Flask,
        emitter: User,
    ):
        """The GET on /biz/missions/new must render the category
        selector with the 3 enum values + the static templates for
        each sub-list so Alpine can pick the right one (#0185)."""
        client = make_authenticated_client(app, emitter)
        response = client.get("/biz/missions/new")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Type de mission" in body
        for value in ("journalisme", "communication", "innovation"):
            assert f'value="{value}"' in body, (
                f"category option {value} missing in the form"
            )
        # Communication / Innovation sub-types remain hardcoded.
        for sub in ("Campagne RP", "Outil IA"):
            assert sub in body, f"sub-option {sub!r} missing in form template"

    def test_journalism_subtype_sourced_from_genres_ontology(
        self,
        app: Flask,
        emitter: User,
    ):
        """Ticket #0201 — the journalism sub-type select must be
        populated from the `genres` taxonomy, not the legacy hardcoded
        list (« Pige / Reportage », « Enquête »…)."""
        client = make_authenticated_client(app, emitter)
        # Stub the taxonomy so we don't depend on prod ontology data.
        fake_genres = ["Portrait test #0201", "Brève test #0201"]
        with patch(
            "app.modules.biz.views.missions.get_taxonomy",
            return_value=fake_genres,
        ):
            response = client.get("/biz/missions/new")

        assert response.status_code == 200
        body = response.data.decode()
        for sub in fake_genres:
            assert sub in body, (
                f"genres ontology entry {sub!r} should populate the "
                "journalism sub-type select"
            )

    def test_category_and_subcategory_surface_on_card_and_detail(
        self,
        app: Flask,
        emitter: User,
        db_session: Session,
    ):
        mission = MissionOffer(
            title="Mission #0185 surface",
            description="<p>Test</p>",
            sector="tech",
            location="Paris",
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=emitter.id,
            emitter_org_id=emitter.organisation_id,
            category=MissionCategory.JOURNALISME,
            subcategory="Pige / Reportage",
        )
        db_session.add(mission)
        db_session.commit()

        client = make_authenticated_client(app, emitter)

        listing = client.get("/biz/?current_tab=missions")
        assert listing.status_code == 200
        body = listing.data.decode()
        assert "Journalisme" in body, "category must surface on the listing card"
        assert "Pige / Reportage" in body, (
            "sub-category must surface on the listing card"
        )

        detail = client.get(f"/biz/missions/{mission.id}")
        assert detail.status_code == 200
        body = detail.data.decode()
        assert "Type de mission" in body
        assert "Journalisme" in body
        assert "Pige / Reportage" in body


class TestJournalismVisibilityRestriction:
    """Bug #0186 (Erick, 2026-06-04) — MARKET/MISSIONS/MISSIONS
    JOURNALISME : « seuls les journalistes peuvent les poster et les
    voir. Les autres communautés n'ont pas à savoir ce que postent
    les journalistes ni qui y répond. »

    A community-level (not BW-level) visibility gate :
    - only PRESS_MEDIA users see Journalism missions in the listing ;
    - the detail page returns 404 (not 403, to avoid leaking
      existence) for non-journalists ;
    - the apply route refuses non-journalist candidates ;
    - the deposit POST refuses a non-journalist trying to create one.

    Other categories (Communication, Innovation) stay visible to
    every authenticated user.
    """

    @pytest.fixture
    def journalism_mission(
        self, db_session: Session, emitter: User, org: Organisation
    ) -> MissionOffer:
        mission = MissionOffer(
            title="Mission Journalisme — visibilité restreinte",
            description="<p>Pige investigation IA</p>",
            sector="media",
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=emitter.id,
            emitter_org_id=org.id,
            category=MissionCategory.JOURNALISME,
            subcategory="Enquête",
        )
        db_session.add(mission)
        db_session.commit()
        return mission

    @pytest.fixture
    def communication_mission(
        self, db_session: Session, emitter: User, org: Organisation
    ) -> MissionOffer:
        mission = MissionOffer(
            title="Mission Communication — visible à tous",
            description="<p>Stratégie RP</p>",
            sector="media",
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=emitter.id,
            emitter_org_id=org.id,
            category=MissionCategory.COMMUNICATION,
            subcategory="Campagne RP",
        )
        db_session.add(mission)
        db_session.commit()
        return mission

    @pytest.fixture
    def non_journalist_user(self, db_session: Session) -> User:
        """A user with no PRESS_MEDIA role — e.g. PR_RELATIONS or
        EXPERT — should not see Journalism missions."""
        pr_role_name = "PRESS_RELATIONS"
        role = db_session.query(Role).filter_by(name=pr_role_name).first()
        if role is None:
            role = Role(name=pr_role_name, description="press relations")
            db_session.add(role)
            db_session.flush()
        user = User(email=_unique_email(), active=True)
        user.photo = b""
        user.roles.append(role)
        db_session.add(user)
        db_session.commit()
        return user

    # ---- Listing -------------------------------------------------------

    def test_journalist_sees_journalism_mission_in_listing(
        self,
        app: Flask,
        emitter: User,
        journalism_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, emitter)
        response = client.get("/biz/?current_tab=missions")
        assert response.status_code == 200
        assert journalism_mission.title.encode() in response.data

    def test_non_journalist_does_not_see_journalism_mission_in_listing(
        self,
        app: Flask,
        non_journalist_user: User,
        journalism_mission: MissionOffer,
        communication_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, non_journalist_user)
        response = client.get("/biz/?current_tab=missions")
        assert response.status_code == 200
        # Journalism mission must NOT appear.
        assert journalism_mission.title.encode() not in response.data, (
            "Journalism missions must be hidden from non-journalists (#0186)"
        )
        # Communication mission stays visible.
        assert communication_mission.title.encode() in response.data, (
            "Non-journalism categories must stay visible to everyone (#0186)"
        )

    # ---- Detail --------------------------------------------------------

    def test_journalist_can_open_journalism_mission_detail(
        self,
        app: Flask,
        emitter: User,
        journalism_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, emitter)
        response = client.get(f"/biz/missions/{journalism_mission.id}")
        assert response.status_code == 200

    def test_non_journalist_gets_404_on_journalism_mission_detail(
        self,
        app: Flask,
        non_journalist_user: User,
        journalism_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, non_journalist_user)
        response = client.get(f"/biz/missions/{journalism_mission.id}")
        # 404, not 403 — avoid leaking the existence of the row
        # (Erick : « n'ont pas à savoir ce que postent les
        # journalistes »).
        assert response.status_code == 404, (
            "Journalism mission detail must 404 for non-journalists, "
            "not 403, to avoid leaking the row's existence (#0186)"
        )

    def test_communication_mission_detail_open_to_all(
        self,
        app: Flask,
        non_journalist_user: User,
        communication_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, non_journalist_user)
        response = client.get(f"/biz/missions/{communication_mission.id}")
        assert response.status_code == 200

    # ---- Apply ---------------------------------------------------------

    def test_non_journalist_cannot_apply_to_journalism_mission(
        self,
        app: Flask,
        non_journalist_user: User,
        journalism_mission: MissionOffer,
        db_session: Session,
    ):
        client = make_authenticated_client(app, non_journalist_user)
        with patch(
            "app.modules.biz.views._offers_common.notify_emitter_of_application"
        ) as mock_notify:
            response = client.post(
                f"/biz/missions/{journalism_mission.id}/apply",
                data={"message": "Test interdit"},
                follow_redirects=False,
            )
        # Either 404 (consistent with the detail gate) or 403 — what
        # matters is no application is persisted and no mail is sent.
        assert response.status_code in (302, 403, 404)
        count = (
            db_session.query(OfferApplication)
            .filter_by(offer_id=journalism_mission.id)
            .count()
        )
        assert count == 0
        mock_notify.assert_not_called()

    # ---- Decision / lifecycle endpoints (Bug #0224) --------------------
    #
    # #0186 gated the listing / detail / apply / deposit, but left the
    # select / reject / fill POST endpoints open — a non-journalist who
    # guessed a mission id could drive its lifecycle. The gate fires
    # right after `get_offer_or_404`, before any application lookup, so a
    # dummy app_id still 404s on the mission (existence stays hidden).

    def test_non_journalist_gets_404_on_journalism_mission_fill(
        self,
        app: Flask,
        non_journalist_user: User,
        journalism_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, non_journalist_user)
        response = client.post(
            f"/biz/missions/{journalism_mission.id}/fill", follow_redirects=False
        )
        assert response.status_code == 404

    def test_non_journalist_gets_404_on_journalism_application_select(
        self,
        app: Flask,
        non_journalist_user: User,
        journalism_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, non_journalist_user)
        response = client.post(
            f"/biz/missions/{journalism_mission.id}/applications/999999/select",
            data={"decision_message": "x"},
            follow_redirects=False,
        )
        assert response.status_code == 404

    def test_non_journalist_gets_404_on_journalism_application_reject(
        self,
        app: Flask,
        non_journalist_user: User,
        journalism_mission: MissionOffer,
    ):
        client = make_authenticated_client(app, non_journalist_user)
        response = client.post(
            f"/biz/missions/{journalism_mission.id}/applications/999999/reject",
            data={"decision_message": "x"},
            follow_redirects=False,
        )
        assert response.status_code == 404

    # ---- Posting -------------------------------------------------------

    def test_non_journalist_cannot_post_journalism_mission(
        self,
        app: Flask,
        non_journalist_user: User,
        db_session: Session,
    ):
        client = make_authenticated_client(app, non_journalist_user)
        response = client.post(
            "/biz/missions/new",
            data={
                "title": "Mission interdite",
                "description": "Une description suffisamment longue pour le test.",
                "sector": "media",
                "category": "journalisme",
                "subcategory": "Enquête",
                "budget_min": "500",
                "budget_max": "1500",
            },
            follow_redirects=False,
        )
        # Either 302 with flash error / 403 — what matters : no
        # Journalism mission is created by a non-journalist.
        assert response.status_code in (200, 302, 403)
        count = (
            db_session.query(MissionOffer).filter_by(title="Mission interdite").count()
        )
        assert count == 0, (
            "non-journalists must not be able to publish a Journalism mission (#0186)"
        )


class TestJournalismMissionExtendedFields:
    """Bug #0187 (Erick, 2026-06-04) — extension of the JOURNALISME
    deposit form :

    > Rajouter les taxonomies : Métiers du journalisme, Types
    > d'entreprises de presse & médias, Types presse & médias,
    > Compétences en journalisme, Langues, Types de contenus
    > éditoriaux, Taille des contenus éditoriaux, Modes de
    > rémunération
    > Rajouter l'option : "La mission doit s'effectuer physiquement
    > ici" / "La mission doit s'effectuer en télétravail"

    All 8 taxonomy fields land as JSON lists ; the 2 work-mode flags
    are booleans. Form accepts comma-separated free text per
    taxonomy in v0 (no ontology dependency yet — Erick's spec calls
    out 8 lists but the ontologies aren't seeded). The fields appear
    only when category is JOURNALISME (via Alpine x-show wrapping)
    but the model accepts them on any mission for future flexibility.
    """

    def test_form_persists_all_extended_fields_for_journalism_mission(
        self,
        app: Flask,
        emitter: User,
        db_session: Session,
    ):
        client = make_authenticated_client(app, emitter)
        # Multi-select fields submit one form value per selected
        # entry — Flask test client takes a list to express that.
        response = client.post(
            "/biz/missions/new",
            data={
                "title": "Mission journalisme étendue",
                "description": "Une description suffisamment longue pour le test.",
                "sector": "media",
                "category": "journalisme",
                "subcategory": "Enquête",
                "metiers_journalisme": ["Reporter", "Rédacteur en chef"],
                "types_entreprises_presse_medias": ["Quotidien régional"],
                "types_presse_medias": ["Print", "Web"],
                "competences_journalisme": ["Investigation", "IA"],
                "langues": ["Français", "Anglais"],
                "types_contenus_editoriaux": ["Long-format"],
                "taille_contenus_editoriaux": ["Article moyen"],
                "modes_remuneration": ["Forfait", "Au feuillet"],
                "physical_required": "y",
                "remote_required": "y",
                "budget_min": "500",
                "budget_max": "1500",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302, response.data[:500]

        mission = (
            db_session.query(MissionOffer)
            .filter_by(title="Mission journalisme étendue")
            .first()
        )
        assert mission is not None
        # The 8 taxonomy columns store JSON lists.
        assert mission.metiers_journalisme == ["Reporter", "Rédacteur en chef"]
        assert mission.types_entreprises_presse_medias == ["Quotidien régional"]
        assert mission.types_presse_medias == ["Print", "Web"]
        assert mission.competences_journalisme == ["Investigation", "IA"]
        assert mission.langues == ["Français", "Anglais"]
        assert mission.types_contenus_editoriaux == ["Long-format"]
        assert mission.taille_contenus_editoriaux == ["Article moyen"]
        assert mission.modes_remuneration == ["Forfait", "Au feuillet"]
        # The 2 work-mode flags.
        assert mission.physical_required is True
        assert mission.remote_required is True

    def test_back_compat_without_extended_fields(
        self,
        app: Flask,
        emitter: User,
        db_session: Session,
    ):
        """A mission posted without the extended fields still
        publishes — they default to empty list / False."""
        client = make_authenticated_client(app, emitter)
        response = client.post(
            "/biz/missions/new",
            data={
                "title": "Mission journalisme minimaliste",
                "description": "Une description suffisamment longue pour le test.",
                "sector": "media",
                "category": "journalisme",
                "subcategory": "Pige / Reportage",
                "budget_min": "500",
                "budget_max": "1500",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        mission = (
            db_session.query(MissionOffer)
            .filter_by(title="Mission journalisme minimaliste")
            .first()
        )
        assert mission is not None
        assert mission.metiers_journalisme == []
        assert mission.langues == []
        assert mission.physical_required is False
        assert mission.remote_required is False

    def test_form_renders_multi_select_widgets_backed_by_ontologies(
        self,
        app: Flask,
        emitter: User,
    ):
        """Each Journalism taxonomy field renders a `<select multiple>`
        whose options come from the matching KYC ontology. Options
        may be empty when the ontology hasn't been seeded yet — the
        important pin is that the form chrome is in place + the
        widgets are `<select multiple>` (not `<input>` legacy)."""
        client = make_authenticated_client(app, emitter)
        response = client.get("/biz/missions/new")
        assert response.status_code == 200
        body = response.data.decode()
        for field_name in (
            "metiers_journalisme",
            "types_entreprises_presse_medias",
            "types_presse_medias",
            "competences_journalisme",
            "langues",
            "types_contenus_editoriaux",
            "taille_contenus_editoriaux",
            "modes_remuneration",
        ):
            # WTForms emits attributes in alphabetical order : the
            # opening tag is `<select class="…" id="…" multiple
            # name="…" size="…">`. Match attribute presence rather
            # than ordering.
            pattern = re.compile(
                r'<select\b[^>]*\bid="' + field_name + r'"[^>]*\bmultiple\b[^>]*>',
                re.DOTALL,
            )
            assert pattern.search(body), (
                f"{field_name} must be a `<select multiple>` (not a legacy <input>)"
            )

    def test_extended_fields_surface_on_detail_page(
        self,
        app: Flask,
        emitter: User,
        db_session: Session,
    ):
        mission = MissionOffer(
            title="Mission journalisme avec profil",
            description="<p>Test</p>",
            sector="media",
            status=PublicationStatus.PUBLIC,
            mission_status=MissionStatus.OPEN,
            owner_id=emitter.id,
            emitter_org_id=emitter.organisation_id,
            category=MissionCategory.JOURNALISME,
            subcategory="Enquête",
            metiers_journalisme=["Reporter"],
            competences_journalisme=["Investigation"],
            langues=["Français"],
            physical_required=True,
            remote_required=False,
        )
        db_session.add(mission)
        db_session.commit()

        client = make_authenticated_client(app, emitter)
        response = client.get(f"/biz/missions/{mission.id}")
        assert response.status_code == 200
        body = response.data.decode()
        assert "Profil recherché" in body
        assert "Reporter" in body
        assert "Investigation" in body
        assert "Français" in body
        assert "Présence physique requise" in body
        # Télétravail chip absent (flag False).
        assert "Télétravail" not in body
