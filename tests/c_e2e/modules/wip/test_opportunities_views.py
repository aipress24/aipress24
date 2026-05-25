# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP opportunities views."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    StatutAvis,
)
from app.modules.wip.views.opportunities import MediaOpportunity
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def journalist_user(db_session: Session, test_org: Organisation) -> User:
    """Create a journalist user who creates avis d'enquete."""
    # Check if role exists
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    match_making = {"fonctions_journalisme": ["Journaliste"]}
    profile = KYCProfile(match_making=match_making)
    user = User(
        email="journalist@example.com",
        first_name="Jane",
        last_name="Journalist",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_avis_enquete(
    db_session: Session,
    journalist_user: User,
    test_org: Organisation,
) -> AvisEnquete:
    """Create a test AvisEnquete."""
    now = datetime.now(UTC)
    avis = AvisEnquete(
        titre="Test Enquête",
        contenu="Looking for experts on AI",
        owner_id=journalist_user.id,
        media_id=test_org.id,
        commanditaire_id=journalist_user.id,
        date_debut_enquete=now - timedelta(days=1),
        date_fin_enquete=now + timedelta(days=7),
        date_bouclage=now + timedelta(days=10),
        date_parution_prevue=now + timedelta(days=14),
    )
    db_session.add(avis)
    db_session.commit()
    return avis


@pytest.fixture
def test_contact(
    db_session: Session,
    test_avis_enquete: AvisEnquete,
    journalist_user: User,
    test_user: User,
) -> ContactAvisEnquete:
    """Create a ContactAvisEnquete linking journalist to expert (test_user)."""
    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=journalist_user.id,
        expert_id=test_user.id,
        status=StatutAvis.EN_ATTENTE,
    )
    db_session.add(contact)
    db_session.commit()
    return contact


class TestOpportunitiesListPage:
    """Tests for the opportunities list page."""

    def test_opportunities_page_loads(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test that opportunities page loads successfully."""
        response = logged_in_client.get("/wip/opportunities")
        assert response.status_code == 200

    def test_opportunities_page_shows_contacts(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
    ):
        """Test that opportunities page shows user's contacts."""
        response = logged_in_client.get("/wip/opportunities")
        assert response.status_code == 200
        html = response.data.decode()
        # Should show the enquete title
        assert "Test Enquête" in html

    def test_opportunities_page_empty_when_no_contacts(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test opportunities page renders with no contacts."""
        response = logged_in_client.get("/wip/opportunities")
        assert response.status_code == 200


class TestOpportunityDetail:
    """Tests for viewing a single opportunity."""

    def test_view_opportunity_success(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
    ):
        """Test viewing own opportunity."""
        response = logged_in_client.get(f"/wip/opportunities/{test_contact.id}")
        assert response.status_code == 200

    def test_view_opportunity_other_user_redirects(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_avis_enquete: AvisEnquete,
        journalist_user: User,
        db_session: Session,
    ):
        """Following the avis-d'enquête notification link as the wrong
        user used to render an empty body (blank page in the browser).
        It now redirects to the opportunities list with a flash."""
        other_expert = User(
            email="other-expert@example.com",
            first_name="Other",
            last_name="Expert",
            active=True,
        )
        db_session.add(other_expert)
        db_session.flush()

        other_contact = ContactAvisEnquete(
            avis_enquete_id=test_avis_enquete.id,
            journaliste_id=journalist_user.id,
            expert_id=other_expert.id,
            status=StatutAvis.EN_ATTENTE,
        )
        db_session.add(other_contact)
        db_session.commit()

        response = logged_in_client.get(f"/wip/opportunities/{other_contact.id}")
        assert response.status_code == 302
        assert response.location.endswith("/wip/opportunities")
        # The response body must not be empty — the original bug was
        # a blank page; we now always send the user *somewhere*.
        assert response.data != b""

    def test_view_opportunity_anonymous_redirects_to_login(
        self,
        client: FlaskClient,
    ):
        """An anonymous visitor clicking the email link must be sent
        to the login page (with a `next=` round-trip) rather than
        getting a silent blank page. The contact id need not exist —
        the anonymous check runs before the DB lookup, on purpose,
        so an expired email link still routes the user through auth.
        """
        response = client.get("/wip/opportunities/123")
        assert response.status_code == 302
        # The exact login URL is Flask-Security config-driven; accept
        # either `/auth/login` or the Flask-Login default `/login`.
        assert "login" in response.location
        # And the destination is NOT the empty page that used to ship.
        assert response.data != b""

    def test_view_opportunity_unknown_id_returns_404(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
    ):
        """An id that doesn't match any contact row (e.g. old email
        after the row was deleted) returns 404, not a blank page."""
        response = logged_in_client.get("/wip/opportunities/99999999999")
        assert response.status_code == 404


class TestOpportunityUnknownIdDoesNotCrash:
    """Regression (audit 2026-05-15, C4): the POST endpoints used
    `repo.get(id)`, which (Advanced-Alchemy `SQLAlchemySyncRepository`)
    *raises* `NotFoundError` on an unknown id — not the werkzeug 404
    — so a stale/forged contact id 500'd instead of 404'ing. The GET
    sibling already does it right with `get_one_or_none` +
    `abort(404)` (opportunities.py:89); these two had diverged
    (lessons-learned #15).
    """

    def test_post_opportunity_unknown_id_returns_404(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """POST /wip/opportunities/<bogus> → 404, not a 500 stack."""
        response = logged_in_client.post(
            "/wip/opportunities/99999999999",
            data={"reponse1": "oui"},
        )
        assert response.status_code == 404

    def test_post_opportunity_form_unknown_id_returns_404(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """POST /wip/opportunities/<bogus>/form (HTMX partial) → 404,
        not a 500 — `_render_media_opportunity` had the same
        `repo.get(id)` misuse."""
        response = logged_in_client.post(
            "/wip/opportunities/99999999999/form",
            data={"reponse1": "non"},
        )
        assert response.status_code == 404


class TestOpportunityResponse:
    """Tests for submitting opportunity responses."""

    def test_accept_opportunity(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        active_bw,
        db_session: Session,
    ):
        """Test accepting an opportunity."""
        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={
                    "reponse1": "oui",
                    "contribution": "I can help with AI topics",
                },
            )

        assert response.status_code == 302  # Redirect
        assert "/wip/opportunities" in response.location

        # Check status was updated
        db_session.refresh(test_contact)
        assert test_contact.status == StatutAvis.ACCEPTE
        assert test_contact.rdv_notes_expert == "I can help with AI topics"
        assert test_contact.date_reponse is not None

    def test_accept_with_press_relation(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        active_bw,
        db_session: Session,
    ):
        """Test accepting with press relation option."""
        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={
                    "reponse1": "oui_relation_presse",
                    "contribution": "Contact my PR team",
                },
            )

        assert response.status_code == 302

        db_session.refresh(test_contact)
        assert test_contact.status == StatutAvis.ACCEPTE_RELATION_PRESSE

    def test_accept_with_press_relation_picks_user_chosen_email(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        active_bw,
        db_session: Session,
    ):
        """Ticket #0075/2 : when the form rendered a dropdown of press
        contacts, the route must persist the email the user *picked*
        (validated against the current valid set), not whichever one
        the service returned first."""
        # Seed an internal BWPRi (Layelle) for the active BW so the
        # service's valid set includes a known email we can pick.
        layelle = User(
            email="layelle-bwpri@example.com",
            first_name="Layelle",
            last_name="LeKun",
            active=True,
        )
        layelle.organisation = test_user.organisation
        layelle.organisation_id = test_user.organisation_id
        db_session.add(layelle)
        db_session.flush()
        db_session.add(
            RoleAssignment(
                business_wall_id=active_bw.id,
                user_id=layelle.id,
                role_type=BWRoleType.BWPRI.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )
        db_session.commit()

        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={
                    "reponse1": "oui_relation_presse",
                    "contribution": "Contact my PR team",
                    "email_relation_presse": "layelle-bwpri@example.com",
                },
            )
        assert response.status_code == 302
        db_session.refresh(test_contact)
        assert test_contact.email_relation_presse == "layelle-bwpri@example.com"

    def test_accept_with_press_relation_rejects_tampered_email(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        active_bw,
        db_session: Session,
    ):
        """Ticket #0075/2 : a POST carrying an email NOT in the valid
        set (form tampering) must fall back to the service's pick,
        never persist the arbitrary address."""
        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={
                    "reponse1": "oui_relation_presse",
                    "contribution": "Contact my PR team",
                    "email_relation_presse": "attacker@evil.com",
                },
            )
        assert response.status_code == 302
        db_session.refresh(test_contact)
        assert test_contact.email_relation_presse != "attacker@evil.com"

    def test_refuse_opportunity(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        active_bw,
        db_session: Session,
    ):
        """Test refusing an opportunity."""
        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={"reponse1": "non"},
            )

        assert response.status_code == 302

        db_session.refresh(test_contact)
        assert test_contact.status == StatutAvis.REFUSE

    def test_refuse_with_suggestion(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        active_bw,
        db_session: Session,
    ):
        """Test refusing with a suggestion of an org colleague.

        The 'non-mais' answer now requires picking a colleague from the
        expert's organisation (bug #0061). The suggested colleague must
        end up with a new ContactAvisEnquete pointing back to the
        suggesting user via suggested_by_user_id.
        """
        colleague = User(
            email="colleague@example.com",
            first_name="Layelle",
            last_name="Lekun",
            active=True,
        )
        colleague.organisation = test_user.organisation
        colleague.organisation_id = test_user.organisation_id
        db_session.add(colleague)
        db_session.commit()

        with (
            patch(
                "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
            ),
            patch("app.services.emails.base.EmailMessage"),
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={
                    "reponse1": "non-mais",
                    "suggested_colleague_id": str(colleague.id),
                },
            )

        assert response.status_code == 302

        db_session.refresh(test_contact)
        assert test_contact.status == StatutAvis.REFUSE_SUGGESTION
        assert "Layelle" in test_contact.rdv_notes_expert

        chained = (
            db_session.query(ContactAvisEnquete)
            .filter_by(
                avis_enquete_id=test_contact.avis_enquete_id,
                expert_id=colleague.id,
            )
            .one()
        )
        assert chained.suggested_by_user_id == test_user.id
        assert chained.status == StatutAvis.EN_ATTENTE


class TestSuggestColleagueRadioAlwaysClickable:
    """Bug #0075 part 3 (Erick, 2026-05-22) : the « Non, mais je suggère
    une personne de mon organisation mieux placée que moi » radio used
    to be `disabled` + `text-gray-400` when ``eligible_colleagues`` was
    empty. Erick : « La mention est en caractères grisés. On ne peut
    l'activer ». The radio must be clickable in every state.
    """

    def test_radio_not_disabled_when_no_eligible_colleagues(
        self,
        app,
        db_session: Session,
        # `test_user` first to seed the PRESS_MEDIA role before
        # `journalist_user` tries to create it again (the two fixtures
        # disagree on the check-or-create pattern and order matters).
        test_user: User,
        journalist_user: User,
        test_avis_enquete: AvisEnquete,
        active_bw,
    ):
        """The expert is the only member of their org → no eligible
        colleagues. The radio must still render WITHOUT ``disabled``."""
        # Solo org / solo expert so list_eligible_colleagues() returns
        # an empty list. The default `test_user` shares its org with
        # `journalist_user`, which would seed an "eligible" colleague.
        solo_org = Organisation(name="Fake-Solo Expert SARL")
        db_session.add(solo_org)
        db_session.flush()
        # An EXPERT role is required for `first_community()` to resolve
        # when rendering the page header.
        expert_role = db_session.query(Role).filter_by(name=RoleEnum.EXPERT.name).first()
        if expert_role is None:
            expert_role = Role(
                name=RoleEnum.EXPERT.name, description=RoleEnum.EXPERT.value
            )
            db_session.add(expert_role)
            db_session.flush()
        solo_expert = User(
            email="solo-expert@example.com",
            first_name="Solo",
            last_name="Expert",
            active=True,
        )
        solo_expert.organisation = solo_org
        solo_expert.organisation_id = solo_org.id
        solo_expert.roles.append(expert_role)
        db_session.add(solo_expert)
        db_session.flush()

        # Active BW so the #0164 gate doesn't hide the response form.
        solo_bw = BusinessWall(
            bw_type="leaders_experts",
            status=BWStatus.ACTIVE.value,
            owner_id=solo_expert.id,
            payer_id=solo_expert.id,
            organisation_id=solo_org.id,
            name="Solo Expert BW",
        )
        db_session.add(solo_bw)
        db_session.flush()
        solo_org.bw_id = solo_bw.id

        contact = ContactAvisEnquete(
            avis_enquete_id=test_avis_enquete.id,
            journaliste_id=journalist_user.id,
            expert_id=solo_expert.id,
            status=StatutAvis.EN_ATTENTE,
        )
        db_session.add(contact)
        db_session.commit()

        client = make_authenticated_client(app, solo_expert)
        response = client.get(f"/wip/opportunities/{contact.id}")
        assert response.status_code == 200
        html = response.data.decode()
        # The radio for « non-mais » must be present and not disabled.
        # We search for the id and check the absence of `disabled` in
        # the same `<input>` tag.
        m = re.search(r'<input\b[^>]*\bid="non-mais"[^>]*>', html)
        assert m is not None, "« non-mais » radio missing from the form"
        assert "disabled" not in m.group(0), (
            f"« non-mais » radio must not be disabled (#0075/3): {m.group(0)}"
        )
        # The label must not be greyed out either.
        label_m = re.search(r'<label\b[^>]*\bfor="non-mais"[^>]*>', html)
        assert label_m is not None
        assert "text-gray-400" not in label_m.group(0), (
            f"« non-mais » label must not be greyed out (#0075/3): "
            f"{label_m.group(0)}"
        )
        # Bug #0071 part 1 (Erick, 2026-05-21) : the form must not
        # surface a confusing « aucun collègue disponible » / « écrivez-
        # nous: contact@aipress24.com » fallback that the user has no
        # way to act on. Was an empty-state hint inside the radio
        # label ; gone now (#0075/3) but guard it explicitly.
        assert "aucun collègue" not in html.lower(), (
            "media_opportunity form must not surface a "
            "« aucun collègue disponible » hint (#0071 part 1)"
        )
        assert "contact@aipress24.com" not in html, (
            "media_opportunity form must not surface "
            "« écrivez-nous: contact@aipress24.com » (#0071 part 1)"
        )


class TestOpportunityResponseRequiresActiveBW:
    """Bug #0164 (Sushanto, 2026-05-20): a user without an active
    Business Wall could submit a response and have it silently lost
    (it persisted only once a BW had been created). Block upstream
    with a clear message instead of dropping the response.
    """

    def test_post_without_bw_does_not_persist_response(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        db_session: Session,
    ):
        """POSTing a response when the expert's org has no active BW
        must NOT mutate the contact's status."""
        with patch(
            "app.modules.wip.views.opportunities.send_avis_enquete_acceptance_email"
        ):
            response = logged_in_client.post(
                f"/wip/opportunities/{test_contact.id}",
                data={
                    "reponse1": "oui",
                    "contribution": "I can help",
                },
                follow_redirects=False,
            )

        # Either a redirect back to the opportunity / opportunities page
        # or a 200 with the banner — never a silent persistence.
        assert response.status_code in (200, 302)
        db_session.refresh(test_contact)
        assert test_contact.status == StatutAvis.EN_ATTENTE, (
            "no-BW response must not be silently persisted"
        )
        assert test_contact.date_reponse is None
        assert (test_contact.rdv_notes_expert or "") == ""

    def test_get_without_bw_shows_clear_banner_no_form(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
    ):
        """GET on an opportunity when expert has no active BW must
        show a clear « configurez d'abord un Business Wall » message
        and hide the response form (so the user can't fill it and
        lose the answer)."""
        response = logged_in_client.get(f"/wip/opportunities/{test_contact.id}")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Business Wall" in html
        # The response form (its submit-confirm modal trigger) must NOT
        # appear when the user lacks a BW.
        assert "avis-response-form" not in html


class TestOpportunityFormUpdate:
    """Tests for HTMX form partial updates."""

    def test_form_update_renders_without_saving(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_contact: ContactAvisEnquete,
        db_session: Session,
    ):
        """Test that form update renders without saving data."""
        original_status = test_contact.status

        response = logged_in_client.post(
            f"/wip/opportunities/{test_contact.id}/form",
            data={"reponse1": "oui"},
        )

        assert response.status_code == 200

        # Status should NOT have changed
        db_session.refresh(test_contact)
        assert test_contact.status == original_status


class TestMediaOpportunityClass:
    """Tests for the MediaOpportunity data class."""

    def test_media_opportunity_properties(
        self,
        db_session: Session,
        test_org: Organisation,
    ):
        """Test MediaOpportunity exposes correct properties."""
        # Create journalist inline to avoid fixture ordering issues
        journalist = User(
            email="journalist-for-class-test@example.com",
            first_name="Test",
            last_name="Journalist",
            active=True,
        )
        journalist.organisation = test_org
        db_session.add(journalist)
        db_session.flush()

        now = datetime.now(UTC)
        avis = AvisEnquete(
            titre="Test Enquête",
            contenu="Looking for experts on AI",
            owner_id=journalist.id,
            media_id=test_org.id,
            commanditaire_id=journalist.id,
            date_debut_enquete=now - timedelta(days=1),
            date_fin_enquete=now + timedelta(days=7),
            date_bouclage=now + timedelta(days=10),
            date_parution_prevue=now + timedelta(days=14),
        )
        db_session.add(avis)
        db_session.commit()

        media_opp = MediaOpportunity(
            id=1,
            journaliste=journalist,
            avis_enquete=avis,
        )

        assert media_opp.titre == "Test Enquête"
        assert media_opp.brief == "Looking for experts on AI"
        assert media_opp.journaliste == journalist
