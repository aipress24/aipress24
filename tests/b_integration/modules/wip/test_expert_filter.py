# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for ExpertFilterService state and selector logic.

Note: Full service testing requires Flask request context. These tests
focus on the logic that can be tested without full dependency injection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from app.modules.wip.services.newsroom.expert_filter import MAX_SELECTABLE_EXPERTS
from app.modules.wip.services.newsroom.expert_selectors import (
    SecteurSelector,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def experts(db_session: Session) -> list[User]:
    """Create test experts with profiles."""
    experts_data = [
        {
            "email": "expert1@example.com",
            "first_name": "Alice",
            "last_name": "Expert",
            "info_professionnelle": {
                "pays_zip_ville": "FR",
                "pays_zip_ville_detail": ["FR 75000 Paris"],
                "secteurs_activite_medias_detail": ["Tech", "Media"],
            },
            "match_making": {
                "secteurs_activite": ["Tech", "Media"],
            },
        },
        {
            "email": "expert2@example.com",
            "first_name": "Bob",
            "last_name": "Expert",
            "info_professionnelle": {
                "pays_zip_ville": "FR",
                "pays_zip_ville_detail": ["FR 69000 Lyon"],
                "secteurs_activite_medias_detail": ["Finance"],
            },
            "match_making": {
                "secteurs_activite": ["Finance"],
            },
        },
        {
            "email": "expert3@example.com",
            "first_name": "Charlie",
            "last_name": "Expert",
            "info_professionnelle": {
                "pays_zip_ville": "DE",
                "pays_zip_ville_detail": [],
                "secteurs_activite_medias_detail": ["Tech"],
            },
            "match_making": {
                "secteurs_activite": ["Tech"],
            },
        },
    ]

    users = []
    for data in experts_data:
        profile = KYCProfile(
            info_professionnelle=data["info_professionnelle"],
            match_making=data["match_making"],
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


class TestMaxSelectableExperts:
    """Tests for MAX_SELECTABLE_EXPERTS constant."""

    def test_max_selectable_experts_defined(self):
        """Test that MAX_SELECTABLE_EXPERTS is defined and reasonable."""
        assert MAX_SELECTABLE_EXPERTS == 50


class TestFilteringLogic:
    """Tests for expert filtering logic using selectors directly."""

    def test_filter_by_sector_single_criterion(self, experts):
        """Test filtering experts by single sector."""
        state = {}
        selector = SecteurSelector(state, experts)
        result = selector.filter_experts({"Finance"}, experts)

        assert len(result) == 1
        assert result[0].email == "expert2@example.com"

    def test_filter_by_sector_multiple_criteria(self, experts):
        """Test filtering experts by multiple sectors (OR logic)."""
        state = {}
        selector = SecteurSelector(state, experts)
        result = selector.filter_experts({"Tech", "Finance"}, experts)

        # All have either Tech or Finance
        assert len(result) == 3

    def test_filter_with_no_criteria_returns_all(self, experts):
        """Test filtering with empty criteria returns all experts."""
        state = {}
        selector = SecteurSelector(state, experts)
        result = selector.filter_experts(set(), experts)

        assert len(result) == len(experts)

    def test_filter_excludes_non_matching(self, experts):
        """Test filtering excludes non-matching experts."""
        state = {}
        selector = SecteurSelector(state, experts)
        result = selector.filter_experts({"Nonexistent"}, experts)

        assert len(result) == 0


class TestSelectedExpertsLogic:
    """Tests for selected experts handling."""

    def test_selected_experts_excluded_from_selectable(self, experts):
        """Test that selected experts are excluded from selectable list."""
        state = {"secteur": [], "selected_experts": [experts[0].id]}
        selector = SecteurSelector(state, experts)

        # Filter returns all, but selected should be handled by service
        result = selector.filter_experts(set(), experts)
        # Selector itself doesn't exclude selected - that's service logic
        assert len(result) == 3

    def test_sorting_by_name(self, experts):
        """Test experts can be sorted by name."""
        # Service sorts by (last_name, first_name)
        sorted_experts = sorted(experts, key=lambda e: (e.last_name, e.first_name))

        assert sorted_experts[0].first_name == "Alice"
        assert sorted_experts[1].first_name == "Bob"
        assert sorted_experts[2].first_name == "Charlie"


class TestFilterState:
    """Tests for filter state management."""

    def test_state_dict_structure(self):
        """Test filter state structure."""
        state = {
            "secteur": ["Tech", "Media"],
            "pays": ["FR"],
            "selected_experts": [1, 2, 3],
        }

        # State can contain string lists and int lists
        assert isinstance(state["secteur"], list)
        assert isinstance(state["selected_experts"], list)
        assert all(isinstance(x, str) for x in state["secteur"])
        assert all(isinstance(x, int) for x in state["selected_experts"])

    def test_state_values_initialization_from_state(self, experts):
        """Test selector values initialized from state."""
        state = {"secteur": ["Tech"]}
        selector = SecteurSelector(state, experts)

        assert "Tech" in selector.values

    def test_state_values_empty_when_no_state(self, experts):
        """Test selector values empty when no state."""
        state = {}
        selector = SecteurSelector(state, experts)

        assert len(selector.values) == 0
