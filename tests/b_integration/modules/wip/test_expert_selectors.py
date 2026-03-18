# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for expert selectors."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from app.modules.wip.services.newsroom.expert_selectors import (
    CompetencesGeneralesSelector,
    DepartementSelector,
    FilterOption,
    FonctionSelector,
    LanguesSelector,
    MetierSelector,
    PaysSelector,
    SecteurSelector,
    TailleOrganisationSelector,
    TypeOrganisationSelector,
    VilleSelector,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def experts_with_profiles(db_session: Session) -> list[User]:
    """Create test experts with detailed profiles."""
    experts_data = [
        {
            "email": "expert1@test.com",
            "first_name": "Alice",
            "last_name": "Expert",
            "match_making": {
                "secteurs_activite": ["Tech", "Media"],
                "toutes_fonctions": ["Director", "Manager"],
                "competences": ["Python", "Data Analysis"],
                "type_organisation": ["Startup"],
                "taille_organisation": ["S1"],
                "langues": ["fr", "en"],
            },
            "info_professionnelle": {
                "pays_zip_ville": "FR",
                "pays_zip_ville_detail": ["FR 75000 Paris"],
                "secteurs_activite_medias_detail": ["Tech", "Media"],
                "type_orga_detail": ["Startup"],
                "taille_orga": ["S1"],
            },
        },
        {
            "email": "expert2@test.com",
            "first_name": "Bob",
            "last_name": "Expert",
            "match_making": {
                "secteurs_activite": ["Finance", "Tech"],
                "toutes_fonctions": ["Analyst"],
                "competences": ["Excel", "Finance"],
                "type_organisation": ["Corporate"],
                "taille_organisation": ["S3"],
                "langues": ["fr", "de"],
            },
            "info_professionnelle": {
                "pays_zip_ville": "FR",
                "pays_zip_ville_detail": ["FR 69000 Lyon"],
                "secteurs_activite_medias_detail": ["Finance", "Tech"],
                "type_orga_detail": ["Corporate"],
                "taille_orga": ["S3"],
            },
        },
        {
            "email": "expert3@test.com",
            "first_name": "Charlie",
            "last_name": "Expert",
            "match_making": {
                "secteurs_activite": ["Tech"],
                "toutes_fonctions": ["Developer"],
                "competences": ["Python", "JavaScript"],
                "type_organisation": ["Agency"],
                "taille_organisation": ["S2"],
                "langues": ["en", "es"],
            },
            "info_professionnelle": {
                "pays_zip_ville": "DE",
                "pays_zip_ville_detail": [],
                "secteurs_activite_medias_detail": ["Tech"],
                "type_orga_detail": ["Agency"],
                "taille_orga": ["S2"],
            },
        },
    ]

    users = []
    for data in experts_data:
        profile = KYCProfile(
            match_making=data["match_making"],
            info_professionnelle=data["info_professionnelle"],
        )

        user = User(
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            active=True,
        )
        user.profile = profile
        db_session.add(user)
        users.append(user)

    db_session.flush()
    return users


class TestFilterOption:
    """Tests for FilterOption dataclass."""

    def test_filter_option_creation(self):
        """Test FilterOption can be created with required fields."""
        option = FilterOption(id="tech", label="Technology")

        assert option.id == "tech"
        assert option.label == "Technology"
        assert option.selected == ""

    def test_filter_option_with_selected(self):
        """Test FilterOption with selected status."""
        option = FilterOption(id="tech", label="Technology", selected="selected")

        assert option.selected == "selected"

    def test_filter_option_ordering(self):
        """Test FilterOption ordering by id."""
        option1 = FilterOption(id="a", label="Alpha")
        option2 = FilterOption(id="b", label="Beta")

        assert option1 < option2

    def test_filter_option_immutable(self):
        """Test FilterOption is immutable (frozen)."""
        option = FilterOption(id="tech", label="Technology")

        with pytest.raises(AttributeError):
            option.id = "other"  # type: ignore[misc]


class TestSecteurSelector:
    """Tests for SecteurSelector."""

    def test_get_values_returns_all_sectors(self, experts_with_profiles):
        """Test get_values returns all unique sectors."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert "Tech" in values
        assert "Media" in values
        assert "Finance" in values

    def test_filter_experts_by_sector(self, experts_with_profiles):
        """Test filtering experts by sector."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        result = selector.filter_experts({"Finance"}, experts_with_profiles)

        assert len(result) == 1
        assert result[0].email == "expert2@test.com"

    def test_filter_experts_by_multiple_sectors(self, experts_with_profiles):
        """Test filtering experts by multiple sectors."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        result = selector.filter_experts({"Tech", "Finance"}, experts_with_profiles)

        # All three have either Tech or Finance
        assert len(result) == 3

    def test_filter_with_empty_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestMetierSelector:
    """Tests for MetierSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id."""
        state = {}
        selector = MetierSelector(state, experts_with_profiles)

        assert selector.id == "metier"
        assert selector.label == "Métier"


class TestFonctionSelector:
    """Tests for FonctionSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = FonctionSelector(state, experts_with_profiles)

        assert selector.id == "fonction"
        assert selector.label == "Toutes fonctions"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = FonctionSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestCompetencesGeneralesSelector:
    """Tests for CompetencesGeneralesSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = CompetencesGeneralesSelector(state, experts_with_profiles)

        assert selector.id == "competences"
        assert selector.label == "Compétences générales"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = CompetencesGeneralesSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestTypeOrganisationSelector:
    """Tests for TypeOrganisationSelector."""

    def test_get_values_returns_all_types(self, experts_with_profiles):
        """Test get_values returns all organization types."""
        state = {}
        selector = TypeOrganisationSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert "Startup" in values
        assert "Corporate" in values
        assert "Agency" in values

    def test_filter_experts_by_org_type(self, experts_with_profiles):
        """Test filtering experts by organization type."""
        state = {}
        selector = TypeOrganisationSelector(state, experts_with_profiles)
        result = selector.filter_experts({"Startup"}, experts_with_profiles)

        assert len(result) == 1
        assert result[0].email == "expert1@test.com"


class TestTailleOrganisationSelector:
    """Tests for TailleOrganisationSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id."""
        state = {}
        selector = TailleOrganisationSelector(state, experts_with_profiles)

        assert selector.id == "taille_organisation"


class TestLanguesSelector:
    """Tests for LanguesSelector."""

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = LanguesSelector(state, experts_with_profiles)

        assert selector.id == "langues"
        assert selector.label == "Langues"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = LanguesSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestPaysSelector:
    """Tests for PaysSelector."""

    def test_get_values_returns_all_countries(self, experts_with_profiles):
        """Test get_values returns all countries."""
        state = {}
        selector = PaysSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert "FR" in values
        assert "DE" in values

    def test_filter_experts_by_country(self, experts_with_profiles):
        """Test filtering experts by country."""
        state = {}
        selector = PaysSelector(state, experts_with_profiles)
        result = selector.filter_experts({"FR"}, experts_with_profiles)

        assert len(result) == 2
        emails = [e.email for e in result]
        assert "expert1@test.com" in emails
        assert "expert2@test.com" in emails


class TestDepartementSelector:
    """Tests for DepartementSelector."""

    def test_get_values_empty_when_no_country_selected(self, experts_with_profiles):
        """Test get_values returns empty when no country is selected."""
        state = {}
        selector = DepartementSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert values == set()

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = DepartementSelector(state, experts_with_profiles)

        assert selector.id == "departement"
        assert selector.label == "Département"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = DepartementSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestVilleSelector:
    """Tests for VilleSelector."""

    def test_get_values_empty_when_no_department_selected(self, experts_with_profiles):
        """Test get_values returns empty when no department is selected."""
        state = {}
        selector = VilleSelector(state, experts_with_profiles)
        values = selector.get_values()

        assert values == set()

    def test_selector_has_correct_id(self, experts_with_profiles):
        """Test selector has correct id and label."""
        state = {}
        selector = VilleSelector(state, experts_with_profiles)

        assert selector.id == "ville"
        assert selector.label == "Ville"

    def test_filter_with_no_criteria_returns_all(self, experts_with_profiles):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = VilleSelector(state, experts_with_profiles)
        result = selector.filter_experts(set(), experts_with_profiles)

        assert len(result) == len(experts_with_profiles)


class TestBaseSelectorOptions:
    """Tests for BaseSelector.options property."""

    def test_options_returns_list_of_filter_options(self, experts_with_profiles):
        """Test options returns list of FilterOption."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        options = selector.options

        assert isinstance(options, list)
        assert all(isinstance(opt, FilterOption) for opt in options)

    def test_options_marks_selected_values(self, experts_with_profiles):
        """Test options marks selected values."""
        state = {"secteur": ["Tech"]}
        selector = SecteurSelector(state, experts_with_profiles)
        options = selector.options

        tech_option = next((o for o in options if o.id == "Tech"), None)
        assert tech_option is not None
        assert tech_option.selected == "selected"

    def test_options_sorted_alphabetically(self, experts_with_profiles):
        """Test options are sorted alphabetically ignoring diacritics."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)
        options = selector.options

        # Check options are sorted
        labels = [o.label for o in options]
        assert labels == sorted(labels)


class TestBaseSelectorValues:
    """Tests for BaseSelector.values initialization."""

    def test_values_initialized_from_state(self, experts_with_profiles):
        """Test values are initialized from state."""
        state = {"secteur": ["Tech", "Media"]}
        selector = SecteurSelector(state, experts_with_profiles)

        assert selector.values == {"Tech", "Media"}

    def test_values_empty_when_no_state(self, experts_with_profiles):
        """Test values are empty when no state."""
        state = {}
        selector = SecteurSelector(state, experts_with_profiles)

        assert selector.values == set()

    def test_values_handles_string_state(self, experts_with_profiles):
        """Test values handle string state (single value)."""
        state = {"secteur": "Tech"}
        selector = SecteurSelector(state, experts_with_profiles)

        assert selector.values == {"Tech"}
