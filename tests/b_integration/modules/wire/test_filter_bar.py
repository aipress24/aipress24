# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for wire FilterBar - tests requiring Flask context."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import arrow
import pytest
from flask import Flask, session
from werkzeug.exceptions import BadRequest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.kyc.field_label import country_code_to_country_name
from app.modules.kyc.ontology_loader import get_ontology_content
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.modules.wire.views._filters import (
    FILTER_SPECS,
    FILTER_SPECS_COM,
    FilterBar,
)
from app.services.zip_codes import CountryEntry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def press_role(db_session: Session) -> Role:
    """Create a press media role."""
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.flush()
    return role


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create test organisation."""
    org = Organisation(name="Test Filter Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_user(db_session: Session, press_role: Role, test_org: Organisation) -> User:
    """Create test user."""
    user = User(email="filter_test@example.com")
    user.first_name = "Filter"
    user.last_name = "Tester"
    user.photo = b""
    user.active = True
    user.organisation = test_org
    user.roles.append(press_role)

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def test_articles(
    db_session: Session, test_user: User, test_org: Organisation
) -> list[ArticlePost]:
    """Create test articles with various attributes."""
    articles = []
    sectors = ["tech", "finance", "health"]
    topics = ["news", "analysis", "opinion"]

    for i, (sector, topic) in enumerate(zip(sectors, topics, strict=True)):
        article = ArticlePost(
            title=f"Article {i}",
            content=f"Content {i}",
            status=PublicationStatus.PUBLIC,
            publisher=test_org,
            owner=test_user,
            published_at=arrow.now(),
            sector=sector,
            topic=topic,
        )
        articles.append(article)
        db_session.add(article)

    db_session.flush()
    return articles


@pytest.fixture
def test_press_releases(
    db_session: Session, test_user: User, test_org: Organisation
) -> list[PressReleasePost]:
    """Create test press releases."""
    releases = []
    for i in range(3):
        release = PressReleasePost(
            title=f"Press Release {i}",
            content=f"Content {i}",
            status=PublicationStatus.PUBLIC,
            publisher=test_org,
            owner=test_user,
            published_at=arrow.now(),
        )
        releases.append(release)
        db_session.add(release)

    db_session.flush()
    return releases


@pytest.fixture
def france_country(db_session: Session) -> CountryEntry:
    """Create France country entry for label_function tests."""
    # Clear caches on both country lookup functions
    country_code_to_country_name.cache_clear()
    get_ontology_content.cache.clear()

    country = CountryEntry(iso3="FR", name="France", seq=1)
    db_session.add(country)
    db_session.flush()
    return country


class TestFilterBarInitialization:
    """Test FilterBar initialization with Flask context."""

    def test_filterbar_init_creates_empty_state(self, app: Flask, db_session: Session):
        """Test FilterBar initializes with empty state when no session data."""
        with app.test_request_context():
            bar = FilterBar("wall")

            assert bar.tab == "wall"
            assert bar.state == {}

    def test_filterbar_init_loads_state_from_session(
        self, app: Flask, db_session: Session
    ):
        """Test FilterBar loads existing state from session."""
        with app.test_request_context():
            # Pre-populate session
            session["wire:wall:state"] = (
                '{"filters": [{"id": "sector", "value": "tech"}]}'
            )

            bar = FilterBar("wall")

            assert bar.state["filters"] == [{"id": "sector", "value": "tech"}]

    def test_filterbar_handles_corrupted_session(self, app: Flask, db_session: Session):
        """Test FilterBar handles corrupted JSON in session gracefully."""
        with app.test_request_context():
            session["wire:wall:state"] = "not valid json{"

            bar = FilterBar("wall")

            # Should return empty state instead of crashing
            assert bar.state == {}


class TestFilterBarSessionOperations:
    """Test FilterBar session save/load operations."""

    def test_save_state_persists_to_session(self, app: Flask, db_session: Session):
        """Test save_state writes to session."""
        with app.test_request_context():
            bar = FilterBar("wall")
            bar.state = {"filters": [{"id": "topic", "value": "news"}]}

            bar.save_state()

            assert "wire:wall:state" in session
            # Verify it's valid JSON
            saved = json.loads(session["wire:wall:state"])
            assert saved["filters"][0]["id"] == "topic"

    def test_reset_clears_state(self, app: Flask, db_session: Session):
        """Test reset clears state and saves."""
        with app.test_request_context():
            session["wire:wall:state"] = (
                '{"filters": [{"id": "sector", "value": "tech"}]}'
            )
            bar = FilterBar("wall")

            bar.reset()

            assert bar.state == {}
            saved = json.loads(session["wire:wall:state"])
            assert saved == {}

    def test_set_tag_adds_tag_filter(self, app: Flask, db_session: Session):
        """Test set_tag adds tag filter and saves."""
        with app.test_request_context():
            bar = FilterBar("wall")

            bar.set_tag("python")

            assert bar.has_filter("tag", "python")


class TestFilterBarUpdateState:
    """Test FilterBar update_state method with form data."""

    def test_update_state_toggle_action(self, app: Flask, db_session: Session):
        """Test update_state with toggle action."""
        with app.test_request_context(
            method="POST",
            data={"action": "toggle", "id": "sector", "value": "tech"},
        ):
            bar = FilterBar("wall")

            bar.update_state()

            assert bar.has_filter("sector", "tech")

    def test_update_state_remove_action(self, app: Flask, db_session: Session):
        """Test update_state with remove action."""
        with app.test_request_context(
            method="POST",
            data={"action": "remove", "id": "sector", "value": "tech"},
        ):
            bar = FilterBar("wall")
            bar.add_filter("sector", "tech")

            bar.update_state()

            assert not bar.has_filter("sector", "tech")

    def test_update_state_sort_by_action(self, app: Flask, db_session: Session):
        """Test update_state with sort-by action."""
        with app.test_request_context(
            method="POST",
            data={"action": "sort-by", "value": "likes"},
        ):
            bar = FilterBar("wall")

            bar.update_state()

            assert bar.sort_order == "likes"

    def test_update_state_unknown_action_raises(self, app: Flask, db_session: Session):
        """Test update_state with unknown action raises BadRequest."""
        with app.test_request_context(
            method="POST",
            data={"action": "unknown", "id": "sector", "value": "tech"},
        ):
            bar = FilterBar("wall")

            with pytest.raises(BadRequest):
                bar.update_state()

    def test_update_state_unknown_filter_id_raises(
        self, app: Flask, db_session: Session
    ):
        """Test update_state with unknown filter ID raises BadRequest."""
        with app.test_request_context(
            method="POST",
            data={"action": "toggle", "id": "unknown_filter", "value": "test"},
        ):
            bar = FilterBar("wall")

            with pytest.raises(BadRequest):
                bar.update_state()


class TestFilterBarProperties:
    """Test FilterBar property methods."""

    def test_sorter_property_returns_options(self, app: Flask, db_session: Session):
        """Test sorter property returns formatted options."""
        with app.test_request_context():
            bar = FilterBar("wall")

            sorter = bar.sorter

            assert "options" in sorter
            assert len(sorter["options"]) > 0
            # Check first option structure
            first_opt = sorter["options"][0]
            assert "value" in first_opt
            assert "label" in first_opt
            assert "selected" in first_opt

    def test_sorter_marks_current_as_selected(self, app: Flask, db_session: Session):
        """Test sorter marks current sort option as selected."""
        with app.test_request_context():
            bar = FilterBar("wall")
            bar.state = {"sort-by": "views"}

            sorter = bar.sorter

            views_opt = next(o for o in sorter["options"] if o["value"] == "views")
            assert views_opt["selected"] is True

    def test_active_filters_with_label_function(
        self, app: Flask, db_session: Session, france_country: CountryEntry
    ):
        """Test active_filters applies label_function when available."""
        with app.test_request_context():
            bar = FilterBar("wall")
            bar.state = {"filters": [{"id": "pays_zip_ville", "value": "FR"}]}

            active = bar.active_filters

            assert len(active) == 1
            # Label function should convert FR to France
            assert active[0]["value"] == "FR"
            # label should be transformed to country name
            assert active[0]["label"] == "France"


class TestFilterBarGetFilters:
    """Test FilterBar get_filters methods."""

    def test_get_filters_for_wall_tab(
        self,
        app: Flask,
        db_session: Session,
        test_articles: list[ArticlePost],
    ):
        """Test get_filters returns filter specs for articles."""
        with app.test_request_context():
            bar = FilterBar("wall")

            filters = bar.get_filters()

            # Should have filters based on FILTER_SPECS
            assert isinstance(filters, list)

    def test_get_filters_for_com_tab(
        self,
        app: Flask,
        db_session: Session,
        test_press_releases: list[PressReleasePost],
    ):
        """Test get_filters returns filter specs for press releases."""
        with app.test_request_context():
            bar = FilterBar("com")

            filters = bar.get_filters()

            # Should have filters based on FILTER_SPECS_COM
            assert isinstance(filters, list)

    def test_get_filters_uses_correct_spec_for_tab(
        self, app: Flask, db_session: Session
    ):
        """Test that different tabs use different filter specs."""
        # FILTER_SPECS has more items than FILTER_SPECS_COM
        assert len(FILTER_SPECS) > len(FILTER_SPECS_COM)
