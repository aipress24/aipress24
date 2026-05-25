# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for Avis d'Enquête views.

These tests verify the journalist and expert views for avis d'enquête management.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import arrow
import pytest

from app.enums import RoleEnum
from app.flask.routing import url_for
from app.models.auth import KYCProfile, Role, User
from app.modules.wip.models.newsroom.avis_enquete import (
    AvisEnquete,
    ContactAvisEnquete,
    RDVStatus,
    RDVType,
    StatutAvis,
)
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient

    from app.models.organisation import Organisation


# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def expert_role(fresh_db) -> Role:
    """Create the EXPERT role."""
    db_session = fresh_db.session
    role = Role(name=RoleEnum.EXPERT.name, description=RoleEnum.EXPERT.value)
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def expert_user(fresh_db, test_org: Organisation, expert_role: Role) -> User:
    """Create an expert user."""
    db_session = fresh_db.session
    expert = User(email="expert@example.com")
    expert.photo = b""
    expert.active = True
    expert.organisation = test_org
    expert.organisation_id = test_org.id
    expert.roles.append(expert_role)
    db_session.add(expert)
    db_session.commit()
    return expert


@pytest.fixture
def test_avis_enquete(fresh_db, test_org: Organisation, test_user: User) -> AvisEnquete:
    """Create a test avis d'enquête."""
    db_session = fresh_db.session
    avis = AvisEnquete(
        owner=test_user,
        media=test_org,
        commanditaire_id=test_user.id,
        date_debut_enquete=arrow.get("2025-01-01").datetime,
        date_fin_enquete=arrow.get("2025-02-01").datetime,
        date_bouclage=arrow.get("2025-02-15").datetime,
        date_parution_prevue=arrow.get("2025-03-01").datetime,
    )
    db_session.add(avis)
    db_session.commit()
    return avis


@pytest.fixture
def contact_with_avis(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_user: User,
) -> ContactAvisEnquete:
    """Create a contact linked to the avis d'enquête."""
    db_session = fresh_db.session
    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_user.id,
        status=StatutAvis.EN_ATTENTE,
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def accepted_contact(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_user: User,
) -> ContactAvisEnquete:
    """Create an accepted contact for RDV proposal tests."""
    db_session = fresh_db.session
    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_user.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(UTC),
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def contact_with_rdv_proposed(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_user: User,
) -> ContactAvisEnquete:
    """Create a contact with RDV proposed (waiting for expert to accept)."""
    db_session = fresh_db.session
    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_user.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(UTC),
        rdv_status=RDVStatus.PROPOSED,
        rdv_type=RDVType.PHONE,
        proposed_slots=[
            "2025-04-01T10:00:00+00:00",
            "2025-04-02T14:00:00+00:00",
        ],
        rdv_phone="0123456789",
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def expert_with_fonction(fresh_db, test_org: Organisation, expert_role: Role) -> User:
    """An expert who has a job title (fonction), e.g. "Directrice de la Recherche"."""
    db_session = fresh_db.session
    profile = KYCProfile(profile_label="Directrice de la Recherche")
    expert = User(
        email="aminata@example.com",
        first_name="Aminata",
        last_name="Youkou",
    )
    expert.profile = profile
    expert.photo = b""
    expert.active = True
    expert.organisation = test_org
    expert.organisation_id = test_org.id
    expert.roles.append(expert_role)
    db_session.add(expert)
    db_session.commit()
    return expert


@pytest.fixture
def contact_with_rdv_f2f_confirmed(
    fresh_db,
    test_avis_enquete: AvisEnquete,
    test_user: User,
    expert_with_fonction: User,
) -> ContactAvisEnquete:
    """A confirmed face-to-face (F2F) RDV with an address set."""
    db_session = fresh_db.session
    test_avis_enquete.titre = "TMS nouvelle génération : quand l'IA dope l'exploitation"
    contact = ContactAvisEnquete(
        avis_enquete_id=test_avis_enquete.id,
        journaliste_id=test_user.id,
        expert_id=expert_with_fonction.id,
        status=StatutAvis.ACCEPTE,
        date_reponse=datetime.now(UTC),
        rdv_status=RDVStatus.CONFIRMED,
        rdv_type=RDVType.F2F,
        date_rdv=datetime(2099, 4, 1, 10, 0, tzinfo=UTC),
        rdv_address="12 rue de la Paix, 75002 Paris",
    )
    db_session.add(contact)
    db_session.commit()
    return contact


@pytest.fixture
def expert_logged_in_client(app: Flask, expert_user: User) -> FlaskClient:
    """Provide a logged-in Flask test client for expert."""
    return make_authenticated_client(app, expert_user)


# ----------------------------------------------------------------
# Journalist Views Tests
# ----------------------------------------------------------------


class TestJournalistAvisEnqueteViews:
    """Tests E2E for journalist views."""

    def test_index_loads_successfully(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Index page loads successfully for authenticated journalist."""
        url = url_for("AvisEnqueteWipView:index")
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_create_avis_enquete_form(self, logged_in_client: FlaskClient):
        """Avis d'enquête creation form loads successfully."""
        url = url_for("AvisEnqueteWipView:new")
        response = logged_in_client.get(url)
        assert response.status_code == 200

    @pytest.mark.skip(
        reason="Requires reference data (Secteur, Metier, etc.) initialization"
    )
    def test_ciblage_experts_loads(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Expert targeting (ciblage) page loads successfully.

        Note: This test requires reference data to be populated (Secteur, Metier,
        Fonction, etc.) for the ExpertFilterService selectors to work.
        """
        url = url_for("AvisEnqueteWipView:ciblage", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_ciblage_renders_four_sections(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Bug #0150 phase 2: the page renders the 4 thematic section
        headings Annie asked for. If a refactor drops one, this fails
        before reaching the browser."""
        url = url_for("AvisEnqueteWipView:ciblage", id=test_avis_enquete.id)
        body = logged_in_client.get(url).data.decode()
        for heading in (
            "Secteurs d&#39;activité et types d&#39;organisation",
            "Géolocalisation",
            "Fonctions",
            "Métiers, compétences &amp; langues",
        ):
            assert heading in body, (
                f"Section heading {heading!r} missing from ciblage page"
            )

    def test_ciblage_emits_dual_cascade_containers(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Bug #0150 phase 3: every 2-level selector must render a
        `.dual-select-cascade` container with its data-* payload so
        the in-page `initDualSelectors()` can wire Tom-Select on it.

        If the partial regresses (e.g. someone reverts the class name
        or drops the data-options attribute), Tom-Select never inits
        and the dropdowns stay as raw `<select>` boxes — exactly the
        symptom Annie reported when this shipped.
        """
        url = url_for("AvisEnqueteWipView:ciblage", id=test_avis_enquete.id)
        body = logged_in_client.get(url).data.decode()
        assert (
            body.count(
                'class="aui-field-group mb-4 col-span-1 lg:col-span-2 dual-select-cascade"'
            )
            == 7
        ), (
            "Expected 7 dual-cascade containers (one per 2-level field "
            "Annie listed): secteur, type_organisation, fonction_pol_adm, "
            "fonction_org_priv, fonction_ass_syn, metier, competences."
        )
        # Each container carries its 4 data-* feeds.
        for attr in (
            "data-options=",
            "data-value=",
            "data-second-value=",
            "data-ajax-url=",
        ):
            assert body.count(attr) >= 7, (
                f"Missing {attr!r} on at least one dual cascade — "
                "Tom-Select init would fail to read its payload."
            )
        # And the JSON payload survived inside single-quoted attributes
        # (the recurrent regression mode for this widget).
        assert "data-options='" in body, (
            "data-options attribute must be single-quoted — `tojson` "
            "output's literal `\"` would break a double-quoted attribute "
            "and Tom-Select would fail with a parse error."
        )

    def test_ciblage_flat_selectors_carry_tom_select_class(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Flat selectors (geoloc, taille, langues…) use the
        `.tom-select-it` class so `initFlatSelectors()` picks them up.
        If the macro regresses (e.g. someone drops the class), they
        also degrade to raw `<select>`."""
        url = url_for("AvisEnqueteWipView:ciblage", id=test_avis_enquete.id)
        body = logged_in_client.get(url).data.decode()
        # 10 selectors are flat: pays, departement, ville,
        # type_entreprise_presse_medias, type_presse_et_media,
        # taille_organisation, fonction, fonction_journalisme,
        # competences_journalisme, langues.
        flat_count = body.count('class="tom-select-it"')
        assert flat_count == 10, (
            f"Expected 10 flat selectors with the .tom-select-it class, "
            f"got {flat_count}"
        )

    def test_view_responses(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_avis: ContactAvisEnquete,
    ):
        """Responses page displays contacts."""
        url = url_for("AvisEnqueteWipView:reponses", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200
        # Check response contains expert email
        assert b"expert@example.com" in response.data or b"expert" in response.data

    def test_propose_rdv_form_loads(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        accepted_contact: ContactAvisEnquete,
    ):
        """RDV proposal form loads for accepted contact."""
        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=accepted_contact.id,
        )
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_reponses_page_links_expert_name_to_profile(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_avis: ContactAvisEnquete,
    ):
        """Erick (2026-05-21) : consulter le profil d'un répondant est
        une info critique. Sur la page « Gérer les réponses », le nom
        de chaque répondant doit être cliquable vers son profil."""
        url = url_for("AvisEnqueteWipView:reponses", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200
        html = response.data.decode()
        expert_profile_url = url_for(contact_with_avis.expert)
        assert f'href="{expert_profile_url}"' in html, (
            "Le nom du répondant doit pointer vers son profil"
        )

    def test_rdv_management_links_expert_name_to_profile(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Sur la page « Gérer les RDV », le nom de l'expert dans la
        table doit être cliquable vers son profil."""
        url = url_for("AvisEnqueteWipView:rdv", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200
        html = response.data.decode()
        expert_profile_url = url_for(contact_with_rdv_proposed.expert)
        assert f'href="{expert_profile_url}"' in html

    def test_rdv_details_links_journaliste_and_expert_to_profiles(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Page de détail d'un RDV : les noms du journaliste ET de
        l'expert doivent tous deux être cliquables vers leurs
        profils (Erick 2026-05-21)."""
        url = url_for(
            "AvisEnqueteWipView:rdv_details",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )
        response = logged_in_client.get(url)
        assert response.status_code == 200
        html = response.data.decode()
        journaliste_profile_url = url_for(contact_with_rdv_proposed.journaliste)
        expert_profile_url = url_for(contact_with_rdv_proposed.expert)
        assert f'href="{journaliste_profile_url}"' in html
        assert f'href="{expert_profile_url}"' in html

    def test_propose_rdv_slots_have_calendar_affordance(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        accepted_contact: ContactAvisEnquete,
    ):
        """Bug #0150 (résiduel UX): the RDV slot inputs were bare
        datetime fields — Erick had to "click on the date" to discover
        the picker, inconsistent with the rest of the app. Each slot
        must now expose an explicit calendar-picker button, and the
        form contract (slot_datetime_N) must be unchanged.
        """
        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=accepted_contact.id,
        )
        response = logged_in_client.get(url)
        assert response.status_code == 200
        html = response.data.decode()
        # Explicit, discoverable picker trigger (5 slots).
        assert html.count("rdv-slot-picker") >= 5
        assert "showPicker()" in html
        # Form contract preserved.
        assert 'name="slot_datetime_1"' in html
        assert 'name="slot_datetime_5"' in html

    def test_rdv_management_page(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """RDV management page loads and shows proposed RDV."""
        url = url_for("AvisEnqueteWipView:rdv", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_rdv_details_page(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """RDV details page loads for contact with proposed RDV."""
        url = url_for(
            "AvisEnqueteWipView:rdv_details",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_rdv_details_omits_proposed_slots_list(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_f2f_confirmed: ContactAvisEnquete,
    ):
        """Ticket #0170: once a slot is accepted, the other proposed
        slots are noise on the RDV detail page. Erick : « Autant les
        retirer car cela trouble la lecture ». The block must NOT be
        rendered any more — only the chosen ``date_rdv`` is relevant
        on this view."""
        url = url_for(
            "AvisEnqueteWipView:rdv_details",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_f2f_confirmed.id,
        )
        response = logged_in_client.get(url)
        assert response.status_code == 200
        body = response.data.decode()
        assert "Créneaux proposés" not in body, (
            "RDV details must not show the (now-obsolete) proposed-slots "
            "block — #0170"
        )
        assert "Aucun créneau proposé" not in body, (
            "RDV details must not show the « Aucun créneau proposé » "
            "empty-state — #0170"
        )


# ----------------------------------------------------------------
# Expert Views Tests
# ----------------------------------------------------------------


class TestExpertAvisEnqueteViews:
    """Tests E2E for expert views."""

    def test_expert_can_access_rdv_accept_page(
        self,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can access the RDV acceptance page."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )
        response = expert_logged_in_client.get(url)
        assert response.status_code == 200

    def test_expert_sees_proposed_slots(
        self,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert sees the proposed time slots on accept page."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )
        response = expert_logged_in_client.get(url)
        assert response.status_code == 200
        # Page should contain slot selection elements
        assert b"selected_slot" in response.data or b"slot" in response.data.lower()

    def test_expert_cannot_access_other_expert_rdv(
        self,
        fresh_db,
        app: Flask,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
        expert_role: Role,
        test_org: Organisation,
    ):
        """Expert cannot access another expert's RDV accept page."""
        db_session = fresh_db.session

        # Create a different expert
        other_expert = User(email="other-expert@example.com")
        other_expert.photo = b""
        other_expert.active = True
        other_expert.organisation = test_org
        other_expert.organisation_id = test_org.id
        other_expert.roles.append(expert_role)
        db_session.add(other_expert)
        db_session.commit()

        # Login as the other expert
        other_expert_client = make_authenticated_client(app, other_expert)

        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )
        response = other_expert_client.get(url, follow_redirects=True)

        # Should be redirected with error
        assert response.status_code == 200
        # Should contain error message or be redirected to home
        assert (
            b"autoris" in response.data.lower()
            or b"home" in response.request.path.lower()
            or response.request.path == "/"
        )


class TestRdvDetailsSummaryCompleteness:
    """Ticket #0150: the confirmed-RDV summary was missing the enquête
    title reminder, the media name, the expert's fonction, and — for a
    face-to-face RDV — the address.

    The address omission had a precise root cause: `rdv_details.j2`
    branched on ``rdv_type.name == 'IN_PERSON'`` but the ``RDVType``
    member is ``F2F``, so the address block could never render
    (enum-name mismatch, lessons-learned #11 family — invisible on
    SQLite because the column is a permissive VARCHAR there).
    """

    def test_journalist_summary_includes_all_rdv_context(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_f2f_confirmed: ContactAvisEnquete,
    ):
        """The journalist's RDV summary shows enquête, media, expert
        fonction and the F2F address."""
        url = url_for(
            "AvisEnqueteWipView:rdv_details",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_f2f_confirmed.id,
        )
        response = logged_in_client.get(url)
        assert response.status_code == 200
        body = response.data.decode()
        assert "TMS nouvelle génération" in body  # enquête reminder
        assert "WIP Test Organization" in body  # media name
        assert "Aminata Youkou" in body  # expert
        assert "Directrice de la Recherche" in body  # expert fonction
        assert "12 rue de la Paix, 75002 Paris" in body  # F2F address

    def test_expert_summary_includes_journalist_and_address(
        self,
        app: Flask,
        expert_with_fonction: User,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_f2f_confirmed: ContactAvisEnquete,
    ):
        """The expert's RDV summary shows the journalist, the media
        and the F2F address (ticket #0150, expert side)."""
        client = make_authenticated_client(app, expert_with_fonction)
        url = url_for(
            "AvisEnqueteWipView:rdv_details",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_f2f_confirmed.id,
        )
        response = client.get(url)
        assert response.status_code == 200
        body = response.data.decode()
        assert "John Doe" in body  # journalist name
        assert "WIP Test Organization" in body  # media name
        assert "12 rue de la Paix, 75002 Paris" in body  # F2F address


# ----------------------------------------------------------------
# Access Control Tests
# ----------------------------------------------------------------


class TestAvisEnqueteAccessControl:
    """Tests for access control on avis d'enquête views."""

    def test_unauthenticated_user_redirected(self, app: Flask):
        """Unauthenticated user is redirected to login."""
        client = app.test_client()
        url = url_for("AvisEnqueteWipView:index")
        response = client.get(url, follow_redirects=False)
        # Should redirect to login
        assert response.status_code in [302, 401]

    def test_journalist_can_edit_own_avis(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Journalist can access edit form for their own avis."""
        url = url_for("AvisEnqueteWipView:edit", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_view_avis_enquete_detail(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        """Journalist can view avis detail."""
        url = url_for("AvisEnqueteWipView:get", id=test_avis_enquete.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestStepNavButtons:
    """Ticket #0151: every Avis d'Enquête step shows navigation
    buttons (top & bottom), mirroring the Business Wall stepper.

      voir     → [Liste]                    [Suivant: Modifier]
      modifier → [Liste]                    [Suivant: Cibler les contacts]
      cibler   → [Liste] [Étape précédente] [Suivant: Gérer les réponses]
      reponses → [Liste] [Étape précédente] [Suivant: Gérer les RDV]
      rdv      → [Liste] [Étape précédente]

    "Supprimer" stays in the 3-dot menu (not asserted here).
    """

    _LIST = "Retourner à la liste des Avis d'enquête"
    _PREV = "Retourner à l'étape précédente"

    def _body(self, client: FlaskClient, endpoint: str, avis: AvisEnquete) -> str:
        response = client.get(url_for(endpoint, id=avis.id))
        assert response.status_code == 200
        return response.data.decode()

    def test_voir_step_nav(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        body = self._body(logged_in_client, "AvisEnqueteWipView:get", test_avis_enquete)
        assert body.count(self._LIST) >= 2  # top + bottom
        assert "Étape suivante : Modifier" in body
        assert self._PREV not in body

    def test_modifier_step_nav(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        body = self._body(
            logged_in_client, "AvisEnqueteWipView:edit", test_avis_enquete
        )
        assert body.count(self._LIST) >= 2
        assert "Étape suivante : Cibler les contacts" in body
        assert self._PREV not in body

    def test_ciblage_step_nav(
        self, logged_in_client: FlaskClient, test_avis_enquete: AvisEnquete
    ):
        body = self._body(
            logged_in_client, "AvisEnqueteWipView:ciblage", test_avis_enquete
        )
        assert body.count(self._LIST) >= 2
        assert body.count(self._PREV) >= 2
        assert "Étape suivante : Gérer les réponses" in body

    def test_reponses_step_nav(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        body = self._body(
            logged_in_client, "AvisEnqueteWipView:reponses", test_avis_enquete
        )
        assert body.count(self._LIST) >= 2
        assert body.count(self._PREV) >= 2
        assert "Étape suivante : Gérer les RDV" in body

    def test_rdv_step_nav(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        body = self._body(logged_in_client, "AvisEnqueteWipView:rdv", test_avis_enquete)
        assert body.count(self._LIST) >= 2
        assert body.count(self._PREV) >= 2
        assert "Étape suivante :" not in body  # rdv is the last step


# ----------------------------------------------------------------
# Form Submission Tests
# ----------------------------------------------------------------


class TestAvisEnqueteFormSubmission:
    """Tests for form submissions."""

    def test_propose_rdv_submission(
        self,
        logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        accepted_contact: ContactAvisEnquete,
    ):
        """Journalist can submit RDV proposal form."""
        url = url_for(
            "AvisEnqueteWipView:rdv_propose",
            id=test_avis_enquete.id,
            contact_id=accepted_contact.id,
        )

        form_data = {
            "rdv_type": "PHONE",
            "slot_datetime_1": "2025-04-01T10:00:00",
            "slot_datetime_2": "2025-04-02T14:00:00",
            "rdv_phone": "0123456789",
            "rdv_notes": "Test notes",
        }

        response = logged_in_client.post(url, data=form_data, follow_redirects=False)

        # Should redirect after successful submission
        assert response.status_code == 302

    def test_expert_accept_rdv_submission(
        self,
        fresh_db,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can submit RDV acceptance form."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )

        # Get the first proposed slot (stored as ISO string)
        first_slot = contact_with_rdv_proposed.proposed_slots[0]

        form_data = {
            "selected_slot": first_slot,  # Already ISO format
            "expert_notes": "Looking forward to our meeting",
            "action": "accept",  # to pass through the popup validation step
        }

        response = expert_logged_in_client.post(
            url,
            data=form_data,
            follow_redirects=True,  # check the rediction page content
        )

        # After submission, redirected to the opportunities list table page
        assert response.status_code == 200
        assert b"Opportunit" in response.data

        # Verify RDV status was updated
        fresh_db.session.refresh(contact_with_rdv_proposed)
        assert contact_with_rdv_proposed.rdv_status == RDVStatus.ACCEPTED

    def test_expert_refuse_rdv_submission_using_decline_slot(
        self,
        fresh_db,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can submit RDV acceptance form but refusing all dates."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )

        form_data = {
            "selected_slot": "decline",
            "expert_notes": "no meeting",
            "action": "accept",  # to pass through the popup validation step
        }

        response = expert_logged_in_client.post(
            url,
            data=form_data,
            follow_redirects=True,  # check the rediction page content
        )

        # After submission, redirected to the opportunities list table page
        assert response.status_code == 200
        assert b"Opportunit" in response.data

        # Verify RDV status was updated
        fresh_db.session.refresh(contact_with_rdv_proposed)
        assert contact_with_rdv_proposed.rdv_status == RDVStatus.NO_RDV

    def test_expert_refuse_rdv_submission_using_refuse_button(
        self,
        fresh_db,
        expert_logged_in_client: FlaskClient,
        test_avis_enquete: AvisEnquete,
        contact_with_rdv_proposed: ContactAvisEnquete,
    ):
        """Expert can submit RDV acceptance form but refusing all dates."""
        url = url_for(
            "AvisEnqueteWipView:rdv_accept",
            id=test_avis_enquete.id,
            contact_id=contact_with_rdv_proposed.id,
        )

        # Get the first proposed slot (stored as ISO string)
        slot = contact_with_rdv_proposed.proposed_slots[0]

        form_data = {
            "selected_slot": slot,  # can use any slot when declining
            "expert_notes": "no meeting",
            "action": "refuse",  # to pass through the popup validation step
        }

        response = expert_logged_in_client.post(
            url,
            data=form_data,
            follow_redirects=True,  # check the rediction page content
        )

        # After submission, redirected to the opportunities list table page
        assert response.status_code == 200
        assert b"Opportunit" in response.data

        # Verify RDV status was updated
        fresh_db.session.refresh(contact_with_rdv_proposed)
        assert contact_with_rdv_proposed.rdv_status == RDVStatus.NO_RDV
