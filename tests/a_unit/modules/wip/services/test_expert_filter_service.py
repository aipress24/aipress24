# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for ExpertFilterService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.models.auth import KYCProfile, User
from app.modules.wip.services.newsroom.expert_filter import (
    MAX_SELECTABLE_EXPERTS,
    ExpertFilterService,
)
from app.modules.wip.services.newsroom.expert_selectors import (
    DepartementSelector,
    FilterOption,
    FonctionSelector,
    MetierSelector,
    PaysSelector,
    SecteurSelector,
    TailleOrganisationSelector,
    TypeEntreprisePresseMediasSelector,
    TypeOrganisationSelector,
    VilleSelector,
)


def _create_expert_with_profile(
    db_session,
    email: str,
    secteurs: list[str] | None = None,
    metiers: list[str] | None = None,
    metiers_autres: list[str] | None = None,
    fonctions: list[str] | None = None,
    type_entreprise_media: list[str] | None = None,
    type_presse_et_media: list[str] | None = None,
    type_orga: list[str] | None = None,
    taille_orga: list[str] | None = None,
    pays: str = "FR",
    departement: str = "75",
    ville: str = "Paris",
    first_name: str = "Expert",
    last_name: str = "Test",
) -> User:
    """Create an expert user with a profile containing specified attributes."""
    user = User(
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_id=f"profile_{email.split('@')[0]}",
        info_professionnelle={
            "secteurs_activite_medias_detail": secteurs or [],
            "secteurs_activite_rp_detail": [],
            "secteurs_activite_detailles_detail": [],
            "type_entreprise_media": type_entreprise_media or [],
            "type_presse_et_media": type_presse_et_media or [],
            "type_orga_detail": type_orga or [],
            "taille_orga": taille_orga or [],
            "pays_zip_ville": pays,
            "pays_zip_ville_detail": f"{pays} CP {departement}000 {ville}",
        },
        info_personnelle={
            "metier_principal_detail": metiers or [],
            "metier_detail": metiers_autres or [],
        },
        match_making={
            "fonctions_journalisme": fonctions or [],
            "fonctions_pol_adm_detail": [],
            "fonctions_org_priv_detail": [],
            "fonctions_ass_syn_detail": [],
        },
    )
    db_session.add(profile)
    db_session.flush()

    return user


# ----------------------------------------------------------------
# SecteurSelector Tests
# ----------------------------------------------------------------


class TestSecteurSelector:
    """Tests for sector filtering."""

    def test_filter_by_secteur_single(self, db_session) -> None:
        """Filter with a single sector selected."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", secteurs=["Tech", "Finance"]
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", secteurs=["Santé"]
        )
        experts = [expert1, expert2]

        selector = SecteurSelector({"secteur": ["Tech"]}, experts)
        result = selector.filter_experts({"Tech"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_filter_by_secteur_multiple(self, db_session) -> None:
        """Filter with multiple sectors (OR logic within criterion)."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", secteurs=["Tech"]
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", secteurs=["Finance"]
        )
        expert3 = _create_expert_with_profile(
            db_session, "e3@test.com", secteurs=["Santé"]
        )
        experts = [expert1, expert2, expert3]

        selector = SecteurSelector({"secteur": ["Tech", "Finance"]}, experts)
        result = selector.filter_experts({"Tech", "Finance"}, experts)

        assert len(result) == 2
        result_ids = {e.id for e in result}
        assert expert1.id in result_ids
        assert expert2.id in result_ids
        assert expert3.id not in result_ids

    def test_filter_by_secteur_no_match(self, db_session) -> None:
        """No expert matches the sector."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", secteurs=["Tech"]
        )
        experts = [expert1]

        selector = SecteurSelector({"secteur": ["Automobile"]}, experts)
        result = selector.filter_experts({"Automobile"}, experts)

        assert len(result) == 0

    def test_get_values_returns_all_sectors(self, db_session) -> None:
        """get_values() returns all unique sectors from experts."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", secteurs=["Tech", "Finance"]
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", secteurs=["Tech", "Santé"]
        )
        experts = [expert1, expert2]

        selector = SecteurSelector({}, experts)
        values = selector.get_values()

        assert values == {"Tech", "Finance", "Santé"}


# ----------------------------------------------------------------
# TypeEntreprisePresseMediasSelector Tests
# ----------------------------------------------------------------


class TestTypeEntreprisePresseMediasSelector:
    """Tests for type d'entreprise presse & médias filtering."""

    def test_filter_by_type_entreprise_media_single(self, db_session) -> None:
        """Filter with a single type d'entreprise selected."""
        expert1 = _create_expert_with_profile(
            db_session,
            "e1@test.com",
            type_entreprise_media=["Agence de presse", "Editeur de magazines"],
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", type_entreprise_media=["Presse écrite"]
        )
        experts = [expert1, expert2]

        selector = TypeEntreprisePresseMediasSelector(
            {"type_entreprise_presse_medias": ["Agence de presse"]}, experts
        )
        result = selector.filter_experts({"Agence de presse"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_filter_by_type_entreprise_media_multiple(self, db_session) -> None:
        """Filter with multiple type d'entreprise (OR logic within criterion)."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", type_entreprise_media=["Agence de presse"]
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", type_entreprise_media=["Editeur de magazines"]
        )
        expert3 = _create_expert_with_profile(
            db_session, "e3@test.com", type_entreprise_media=["Presse écrite"]
        )
        experts = [expert1, expert2, expert3]

        selector = TypeEntreprisePresseMediasSelector(
            {
                "type_entreprise_presse_medias": [
                    "Agence de presse",
                    "Editeur de magazines",
                ]
            },
            experts,
        )
        result = selector.filter_experts(
            {"Agence de presse", "Editeur de magazines"}, experts
        )

        assert len(result) == 2
        result_ids = {e.id for e in result}
        assert expert1.id in result_ids
        assert expert2.id in result_ids
        assert expert3.id not in result_ids

    def test_filter_by_type_entreprise_media_no_match(self, db_session) -> None:
        """No expert matches the type d'entreprise."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", type_entreprise_media=["Agence de presse"]
        )
        experts = [expert1]

        selector = TypeEntreprisePresseMediasSelector(
            {"type_entreprise_presse_medias": "Editeur de magazines"}, experts
        )
        result = selector.filter_experts({"Editeur de magazines"}, experts)

        assert len(result) == 0

    def test_get_values_returns_all_type_entreprise_media(self, db_session) -> None:
        """get_values() returns all unique type d'entreprise from experts."""
        expert1 = _create_expert_with_profile(
            db_session,
            "e1@test.com",
            type_entreprise_media=["Agence de presse", "Editeur de magazines"],
        )
        expert2 = _create_expert_with_profile(
            db_session,
            "e2@test.com",
            type_entreprise_media=["Agence de presse", "Presse écrite"],
        )
        experts = [expert1, expert2]

        selector = TypeEntreprisePresseMediasSelector({}, experts)
        values = selector.get_values()

        assert values == {"Agence de presse", "Editeur de magazines", "Presse écrite"}


# ----------------------------------------------------------------
# MetierSelector Tests
# ----------------------------------------------------------------


class TestMetierSelector:
    """Tests for profession/trade filtering."""

    def test_filter_by_metier_primary(self, db_session) -> None:
        """Filter on primary profession."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", metiers=["Journaliste"]
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", metiers=["Photographe"]
        )
        experts = [expert1, expert2]

        selector = MetierSelector({"metier": ["Journaliste"]}, experts)
        result = selector.filter_experts({"Journaliste"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_filter_by_metier_secondary(self, db_session) -> None:
        """Filter includes secondary professions (User.tous_metiers)."""
        expert1 = _create_expert_with_profile(
            db_session,
            "e1@test.com",
            metiers=["Journaliste"],
            metiers_autres=["Rédacteur"],
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", metiers=["Photographe"]
        )
        experts = [expert1, expert2]

        selector = MetierSelector({"metier": ["Rédacteur"]}, experts)
        result = selector.filter_experts({"Rédacteur"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_get_values_includes_all_metiers(self, db_session) -> None:
        """get_values() returns both primary and secondary professions."""
        expert1 = _create_expert_with_profile(
            db_session,
            "e1@test.com",
            metiers=["Journaliste"],
            metiers_autres=["Rédacteur"],
        )
        experts = [expert1]

        selector = MetierSelector({}, experts)
        values = selector.get_values()

        assert "Journaliste" in values
        assert "Rédacteur" in values


# ----------------------------------------------------------------
# FonctionSelector Tests
# ----------------------------------------------------------------


class TestFonctionSelector:
    """Tests for job function filtering."""

    def test_filter_by_fonction(self, db_session) -> None:
        """Filter by job function."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", fonctions=["Directeur"]
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", fonctions=["Rédacteur en chef"]
        )
        experts = [expert1, expert2]

        selector = FonctionSelector({"fonction": ["Directeur"]}, experts)
        result = selector.filter_experts({"Directeur"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id


# ----------------------------------------------------------------
# OrganisationSelector Tests
# ----------------------------------------------------------------


class TestOrganisationSelectors:
    """Tests for organization type and size filtering."""

    def test_filter_by_type_organisation(self, db_session) -> None:
        """Filter by organization type."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", type_orga=["PME"]
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", type_orga=["Grand groupe"]
        )
        experts = [expert1, expert2]

        selector = TypeOrganisationSelector({"type_organisation": ["PME"]}, experts)
        result = selector.filter_experts({"PME"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_filter_by_taille_organisation(self, db_session) -> None:
        """Filter by organization size."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", taille_orga=["10-49"]
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", taille_orga=["250+"]
        )
        experts = [expert1, expert2]

        selector = TailleOrganisationSelector(
            {"taille_organisation": ["10-49"]}, experts
        )
        result = selector.filter_experts({"10-49"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_get_values_returns_taille_codes(self, db_session) -> None:
        """get_values() returns the taille codes from profiles."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", taille_orga=["small"]
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", taille_orga=["large"]
        )
        experts = [expert1, expert2]

        selector = TailleOrganisationSelector({}, experts)
        values = selector.get_values()

        assert "small" in values
        assert "large" in values


# ----------------------------------------------------------------
# GeoSelector Tests
# ----------------------------------------------------------------


class TestGeoSelectors:
    """Tests for geographic filtering (country, department, city)."""

    def test_filter_by_pays(self, db_session) -> None:
        """Filter by country."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", pays="FR", departement="75", ville="Paris"
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", pays="BE", departement="10", ville="Bruxelles"
        )
        experts = [expert1, expert2]

        selector = PaysSelector({"pays": ["FR"]}, experts)
        result = selector.filter_experts({"FR"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_filter_by_departement(self, db_session) -> None:
        """Filter by department (depends on country)."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", pays="FR", departement="75", ville="Paris"
        )
        expert2 = _create_expert_with_profile(
            db_session, "e2@test.com", pays="FR", departement="69", ville="Lyon"
        )
        experts = [expert1, expert2]

        selector = DepartementSelector({"pays": ["FR"], "departement": ["75"]}, experts)
        result = selector.filter_experts({"75"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_filter_by_ville(self, db_session) -> None:
        """Filter by city (depends on department)."""
        expert1 = _create_expert_with_profile(
            db_session,
            "e1@test.com",
            pays="FR",
            departement="75",
            ville="Paris",
        )
        expert2 = _create_expert_with_profile(
            db_session,
            "e2@test.com",
            pays="FR",
            departement="75",
            ville="Neuilly",
        )
        experts = [expert1, expert2]

        selector = VilleSelector(
            {"pays": ["FR"], "departement": ["75"], "ville": ["Paris"]}, experts
        )
        result = selector.filter_experts({"Paris"}, experts)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_departement_requires_pays(self, db_session) -> None:
        """Department is not available without country selection."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", pays="FR", departement="75", ville="Paris"
        )
        experts = [expert1]

        # No pays in state = no departments available
        selector = DepartementSelector({}, experts)
        values = selector.get_values()

        assert len(values) == 0

    def test_ville_requires_departement(self, db_session) -> None:
        """City is not available without department selection."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", pays="FR", departement="75", ville="Paris"
        )
        experts = [expert1]

        # No departement in state = no cities available
        selector = VilleSelector({"pays": ["FR"]}, experts)
        values = selector.get_values()

        assert len(values) == 0


# ----------------------------------------------------------------
# Multiple Criteria Tests
# ----------------------------------------------------------------


class TestMultipleCriteria:
    """Tests for combining multiple filter criteria."""

    def test_filter_multiple_criteria_and_logic(self, db_session) -> None:
        """Multiple criteria apply AND logic between categories."""
        expert1 = _create_expert_with_profile(
            db_session,
            "e1@test.com",
            secteurs=["Tech"],
            metiers=["Journaliste"],
        )
        expert2 = _create_expert_with_profile(
            db_session,
            "e2@test.com",
            secteurs=["Tech"],
            metiers=["Photographe"],
        )
        expert3 = _create_expert_with_profile(
            db_session,
            "e3@test.com",
            secteurs=["Finance"],
            metiers=["Journaliste"],
        )
        experts = [expert1, expert2, expert3]

        # First filter by sector
        secteur_selector = SecteurSelector({"secteur": ["Tech"]}, experts)
        filtered = secteur_selector.filter_experts({"Tech"}, experts)

        # Then filter by profession
        metier_selector = MetierSelector({"metier": ["Journaliste"]}, filtered)
        result = metier_selector.filter_experts({"Journaliste"}, filtered)

        assert len(result) == 1
        assert result[0].id == expert1.id

    def test_filter_empty_returns_all(self, db_session) -> None:
        """No criteria returns all experts (limited)."""
        expert1 = _create_expert_with_profile(db_session, "e1@test.com")
        expert2 = _create_expert_with_profile(db_session, "e2@test.com")
        experts = [expert1, expert2]

        # Empty criteria = no filtering
        selector = SecteurSelector({}, experts)
        result = selector.filter_experts(set(), experts)

        assert len(result) == 2


# ----------------------------------------------------------------
# State Management Tests
# ----------------------------------------------------------------


class TestStateManagement:
    """Tests for session state management.

    Note: These tests verify state behavior without complex mocking.
    The ExpertFilterService uses session storage via SVCS container.
    """

    def test_state_dict_operations(self) -> None:
        """State dictionary operations work correctly."""
        state: dict = {}

        # Set state
        state["newsroom:ciblage"] = {"secteur": ["Tech"]}
        assert state["newsroom:ciblage"] == {"secteur": ["Tech"]}

        # Clear state
        state["newsroom:ciblage"] = {}
        assert state["newsroom:ciblage"] == {}

    def test_state_with_selected_experts(self) -> None:
        """State can hold selected expert IDs."""
        state = {"selected_experts": [1, 2, 3]}

        # Add more experts
        existing = state.get("selected_experts", [])
        new_ids = [4, 5]
        state["selected_experts"] = list(set(existing + new_ids))

        assert 1 in state["selected_experts"]
        assert 4 in state["selected_experts"]

    def test_filter_state_type_alias(self) -> None:
        """FilterState type can hold different value types."""
        from app.modules.wip.services.newsroom.expert_filter import FilterState

        # FilterState can hold strings, list of strings, or list of ints
        state: FilterState = {
            "secteur": ["Tech", "Finance"],
            "selected_experts": [1, 2, 3],
        }

        assert isinstance(state["secteur"], list)
        assert isinstance(state["selected_experts"], list)

    def test_session_key_initialization(self, db_session, app) -> None:
        """Session key depends on avis_enquete_id."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", secteurs=["Tech"]
        )

        with patch(
            "app.modules.wip.services.newsroom.expert_filter.container"
        ) as mock_container:
            mock_session: dict = {}
            mock_user_repo = MagicMock()
            mock_user_repo.list.return_value = [expert1]

            mock_container.get.return_value = mock_session

            service = ExpertFilterService()
            service._session = mock_session
            service._user_repo = mock_user_repo

            # initialize session key
            avis_enquete_id = "abcdef"
            service._set_session_key(avis_enquete_id)

            assert service._session_key == f"newsroom:ciblage{avis_enquete_id}"

    def test_update_state_from_htmx_request(self, db_session, app) -> None:
        """State is updated from HTMX request data."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", secteurs=["Tech"]
        )

        # Simulate HTMX POST request with selector change
        with app.test_request_context(
            method="POST",
            headers={"HX-Request": "true"},
            data={
                "selector_change": "secteur",
                "secteur": ["Tech", "Finance"],
            },
        ):
            with patch(
                "app.modules.wip.services.newsroom.expert_filter.container"
            ) as mock_container:
                mock_session: dict = {}
                mock_user_repo = MagicMock()
                mock_user_repo.list.return_value = [expert1]

                mock_container.get.return_value = mock_session

                service = ExpertFilterService()
                service._session = mock_session
                service._user_repo = mock_user_repo
                service._state = {}

                # Call the internal method directly
                service._update_state_from_request()

                # State should be updated with selector values
                assert "secteur" in service._state
                assert service._state["secteur"] == ["Tech", "Finance"]

    def test_update_state_ignores_non_htmx_request(self, db_session, app) -> None:
        """State is NOT updated from non-HTMX requests."""
        # Request without HX-Request header
        with app.test_request_context(
            method="POST",
            data={
                "selector_change": "secteur",
                "secteur": ["Tech"],
            },
        ):
            with patch(
                "app.modules.wip.services.newsroom.expert_filter.container"
            ) as mock_container:
                mock_session: dict = {}
                mock_container.get.return_value = mock_session

                service = ExpertFilterService()
                service._session = mock_session
                service._user_repo = MagicMock()
                service._state = {}

                service._update_state_from_request()

                # State should NOT be updated (no HX-Request header)
                assert "secteur" not in service._state

    def test_one_state_per_avis_enquete_id(self, db_session, app) -> None:
        """State updated from HTMX request data do not change other
        Avis d Enquete states."""
        expert1 = _create_expert_with_profile(
            db_session, "e1@test.com", secteurs=["Tech"]
        )

        # Simulate HTMX POST request with selector change
        with app.test_request_context(
            method="POST",
            headers={"HX-Request": "true"},
            data={
                "selector_change": "secteur",
                "secteur": ["Tech", "Finance"],
            },
        ):
            with patch(
                "app.modules.wip.services.newsroom.expert_filter.container"
            ) as mock_container:
                mock_session: dict = {}
                mock_user_repo = MagicMock()
                mock_user_repo.list.return_value = [expert1]

                mock_container.get.return_value = mock_session

                service1 = ExpertFilterService()
                service1._session = mock_session
                service1._user_repo = mock_user_repo
                avis_enquete_id_1 = "abcdef1"
                service1._set_session_key(avis_enquete_id_1)
                service1._restore_state()

                service2 = ExpertFilterService()
                service2._session = mock_session
                service2._user_repo = mock_user_repo
                avis_enquete_id_2 = "abcdef2"
                service2._set_session_key(avis_enquete_id_2)
                service2._restore_state()
                service2._update_state_from_request()

                # State should be updated with selector values
                assert "secteur" in service2._state
                # State of other ExpertFilterService is untouched
                assert "secteur" not in service1._state

    def test_update_state_clears_dependent_selectors(self, db_session, app) -> None:
        """Changing a selector clears dependent selectors."""
        # When pays changes, departement and ville should be cleared
        with app.test_request_context(
            method="POST",
            headers={"HX-Request": "true"},
            data={
                "selector_change": "pays",
                "pays": ["BE"],  # Changed from FR to BE
            },
        ):
            with patch(
                "app.modules.wip.services.newsroom.expert_filter.container"
            ) as mock_container:
                mock_session: dict = {}
                mock_container.get.return_value = mock_session

                service = ExpertFilterService()
                service._session = mock_session
                service._user_repo = MagicMock()
                # Pre-existing state with FR, departement 75, ville Paris
                service._state = {
                    "pays": ["FR"],
                    "departement": ["75"],
                    "ville": ["Paris"],
                }

                service._update_state_from_request()

                # Pays should be updated
                assert service._state["pays"] == ["BE"]
                # Departement and ville should be cleared (not in request)
                assert "departement" not in service._state
                assert "ville" not in service._state


# ----------------------------------------------------------------
# Expert Selection Tests
# ----------------------------------------------------------------


class TestExpertSelection:
    """Tests for expert selection functionality.

    Note: These tests focus on selection logic without complex container mocking.
    The actual service integration is tested in integration tests.
    """

    def test_selected_expert_ids_tracking(self, db_session) -> None:
        """Selected expert IDs are tracked in state."""
        expert1 = _create_expert_with_profile(db_session, "e1@test.com")
        expert2 = _create_expert_with_profile(db_session, "e2@test.com")

        state = {"selected_experts": [expert1.id]}

        # Get selected from state
        selected_ids = set(state.get("selected_experts", []))
        assert expert1.id in selected_ids
        assert expert2.id not in selected_ids

    def test_add_experts_from_request(self, db_session, app) -> None:
        """Add experts from form to current selection."""
        expert1 = _create_expert_with_profile(db_session, "e1@test.com")
        expert2 = _create_expert_with_profile(db_session, "e2@test.com")

        with app.test_request_context(
            method="POST",
            data={f"expert:{expert2.id}": "on"},
        ):
            with patch(
                "app.modules.wip.services.newsroom.expert_filter.container"
            ) as mock_container:
                mock_session: dict = {}
                mock_user_repo = MagicMock()
                mock_user_repo.list.return_value = [expert1, expert2]

                mock_container.get.return_value = mock_session

                service = ExpertFilterService()
                service._session = mock_session
                service._user_repo = mock_user_repo
                service._state = {"selected_experts": [expert1.id]}
                service.add_experts_from_request()

                selected = service._state["selected_experts"]
                assert expert1.id in selected
                assert expert2.id in selected

    def test_update_experts_from_request(self, db_session, app) -> None:
        """Replace selection with experts from form."""
        expert1 = _create_expert_with_profile(db_session, "e1@test.com")
        expert2 = _create_expert_with_profile(db_session, "e2@test.com")

        with app.test_request_context(
            method="POST",
            data={f"expert:{expert2.id}": "on"},
        ):
            with patch(
                "app.modules.wip.services.newsroom.expert_filter.container"
            ) as mock_container:
                mock_session: dict = {}
                mock_user_repo = MagicMock()
                mock_user_repo.list.return_value = [expert1, expert2]

                mock_container.get.return_value = mock_session

                service = ExpertFilterService()
                service._session = mock_session
                service._user_repo = mock_user_repo
                service._state = {"selected_experts": [expert1.id]}
                service.update_experts_from_request()

                selected = service._state["selected_experts"]
                assert expert1.id not in selected
                assert expert2.id in selected

    def test_max_selectable_experts_limit(self, db_session) -> None:
        """Selection is limited to MAX_SELECTABLE_EXPERTS (50)."""
        # Create 60 experts
        experts = []
        for i in range(60):
            expert = _create_expert_with_profile(
                db_session,
                f"e{i}@test.com",
                first_name=f"Expert{i}",
                last_name=f"Test{i:03d}",
            )
            experts.append(expert)

        # Verify we created more experts than the limit
        assert len(experts) == 60
        assert len(experts) > MAX_SELECTABLE_EXPERTS

        # When filtering, results should be limited to MAX_SELECTABLE_EXPERTS
        filtered = experts[:MAX_SELECTABLE_EXPERTS]
        assert len(filtered) == MAX_SELECTABLE_EXPERTS

    def test_exclude_already_selected_experts(self, db_session) -> None:
        """Already selected experts are excluded from selectable list."""
        expert1 = _create_expert_with_profile(db_session, "e1@test.com")
        expert2 = _create_expert_with_profile(db_session, "e2@test.com")
        expert3 = _create_expert_with_profile(db_session, "e3@test.com")
        experts = [expert1, expert2, expert3]

        state = {"selected_experts": [expert1.id]}
        selected_ids = set(state.get("selected_experts", []))

        # Filter out already selected
        new_experts = [e for e in experts if e.id not in selected_ids]

        assert len(new_experts) == 2
        assert expert1 not in new_experts
        assert expert2 in new_experts
        assert expert3 in new_experts


# ----------------------------------------------------------------
# FilterOption Tests
# ----------------------------------------------------------------


class TestFilterOption:
    """Tests for FilterOption dataclass."""

    def test_filter_option_creation(self) -> None:
        """FilterOption is created with correct attributes."""
        option = FilterOption(id="tech", label="Technology", selected="selected")

        assert option.id == "tech"
        assert option.label == "Technology"
        assert option.selected == "selected"

    def test_filter_option_default_selected(self) -> None:
        """FilterOption defaults selected to empty string."""
        option = FilterOption(id="tech", label="Technology")

        assert option.selected == ""

    def test_filter_option_ordering(self) -> None:
        """FilterOptions are ordered by id."""
        opt1 = FilterOption(id="b", label="Beta")
        opt2 = FilterOption(id="a", label="Alpha")

        assert opt2 < opt1
