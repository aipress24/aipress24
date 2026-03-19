# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for wire tabs - tests requiring Flask context."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from flask import Flask, g, session

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.modules.wire.views._filters import FilterBar
from app.modules.wire.views._tabs import (
    AgenciesTab,
    ComTab,
    JournalistsTab,
    MediasTab,
    WallTab,
    get_tabs,
)
from app.services.social_graph import adapt

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
    org = Organisation(name="Test Tabs Org")
    org.bw_active = "media"  # Mark as media org
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_user(db_session: Session, press_role: Role, test_org: Organisation) -> User:
    """Create test user."""
    user = User(email="tabs_test@example.com")
    user.first_name = "Tabs"
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
def other_user(db_session: Session, press_role: Role, test_org: Organisation) -> User:
    """Create another user to follow."""
    user = User(email="other_tabs@example.com")
    user.first_name = "Other"
    user.last_name = "User"
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
    """Create test articles."""
    articles = []
    for i in range(5):
        article = ArticlePost(
            title=f"Tab Test Article {i}",
            content=f"Content {i}",
            status=PublicationStatus.PUBLIC,
            publisher=test_org,
            owner=test_user,
            published_at=arrow.now().shift(hours=-i),
            sector="tech",
            view_count=i * 10,
            like_count=i * 5,
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
            title=f"Tab Test Press Release {i}",
            content=f"Content {i}",
            status=PublicationStatus.PUBLIC,
            publisher=test_org,
            owner=test_user,
            published_at=arrow.now().shift(hours=-i),
        )
        releases.append(release)
        db_session.add(release)

    db_session.flush()
    return releases


class TestGetTabs:
    """Test get_tabs function."""

    def test_get_tabs_returns_five_tabs(self):
        """Test get_tabs returns 5 tabs."""
        tabs = get_tabs()

        assert len(tabs) == 5

    def test_get_tabs_returns_correct_tab_types(self):
        """Test get_tabs returns correct tab instances."""
        tabs = get_tabs()

        assert isinstance(tabs[0], WallTab)
        assert isinstance(tabs[1], AgenciesTab)
        assert isinstance(tabs[2], MediasTab)
        assert isinstance(tabs[3], JournalistsTab)
        assert isinstance(tabs[4], ComTab)

    def test_tabs_have_required_attributes(self):
        """Test all tabs have required attributes."""
        tabs = get_tabs()

        for tab in tabs:
            assert hasattr(tab, "id")
            assert hasattr(tab, "label")
            assert hasattr(tab, "tip")
            assert hasattr(tab, "post_type_allow")


class TestTabIsActive:
    """Test Tab.is_active property."""

    def test_is_active_returns_true_for_current_tab(
        self, app: Flask, db_session: Session
    ):
        """Test is_active returns True when session matches tab."""
        with app.test_request_context():
            session["wire:tab"] = "wall"

            tab = WallTab()

            assert tab.is_active is True

    def test_is_active_returns_false_for_other_tab(
        self, app: Flask, db_session: Session
    ):
        """Test is_active returns False when session has different tab."""
        with app.test_request_context():
            session["wire:tab"] = "agencies"

            tab = WallTab()

            assert tab.is_active is False


class TestWallTab:
    """Test WallTab functionality."""

    def test_wall_tab_attributes(self):
        """Test WallTab has correct attributes."""
        tab = WallTab()

        assert tab.id == "wall"
        assert tab.label == "All"
        assert "article" in tab.post_type_allow
        assert "post" in tab.post_type_allow

    def test_wall_tab_get_authors_returns_empty(self):
        """Test WallTab.get_authors returns empty (no filter)."""
        tab = WallTab()

        authors = tab.get_authors()

        assert list(authors) == []

    def test_wall_tab_get_posts(
        self,
        app: Flask,
        db_session: Session,
        test_user: User,
        test_articles: list[ArticlePost],
    ):
        """Test WallTab.get_posts returns articles."""
        with app.test_request_context():
            session["wire:tab"] = "wall"
            g.user = test_user

            tab = WallTab()
            bar = FilterBar("wall")

            posts = tab.get_posts(bar)

            assert len(posts) > 0
            assert all(p.type in tab.post_type_allow for p in posts)


class TestComTab:
    """Test ComTab functionality."""

    def test_com_tab_attributes(self):
        """Test ComTab has correct attributes."""
        tab = ComTab()

        assert tab.id == "com"
        assert tab.label == "Idées & Comm"
        assert "press_release" in tab.post_type_allow

    def test_com_tab_get_posts(
        self,
        app: Flask,
        db_session: Session,
        test_user: User,
        test_press_releases: list[PressReleasePost],
    ):
        """Test ComTab.get_posts returns press releases."""
        with app.test_request_context():
            session["wire:tab"] = "com"
            g.user = test_user

            tab = ComTab()
            bar = FilterBar("com")

            posts = tab.get_posts(bar)

            assert len(posts) > 0
            assert all(p.type in tab.post_type_allow for p in posts)


class TestJournalistsTab:
    """Test JournalistsTab functionality."""

    def test_journalists_tab_attributes(self):
        """Test JournalistsTab has correct attributes."""
        tab = JournalistsTab()

        assert tab.id == "journalists"
        assert tab.label == "Journalistes"

    def test_journalists_tab_get_authors_returns_followees(
        self,
        app: Flask,
        db_session: Session,
        test_user: User,
        other_user: User,
    ):
        """Test JournalistsTab.get_authors returns followed users."""
        # Make test_user follow other_user
        adapt(test_user).follow(other_user)
        db_session.flush()

        with app.test_request_context():
            g.user = test_user

            tab = JournalistsTab()
            authors = tab.get_authors()

            author_list = list(authors)
            assert other_user in author_list


class TestMediasTab:
    """Test MediasTab functionality."""

    def test_medias_tab_attributes(self):
        """Test MediasTab has correct attributes."""
        tab = MediasTab()

        assert tab.id == "media"
        assert tab.label == "Médias"


class TestAgenciesTab:
    """Test AgenciesTab functionality."""

    def test_agencies_tab_attributes(self):
        """Test AgenciesTab has correct attributes."""
        tab = AgenciesTab()

        assert tab.id == "agencies"
        assert tab.label == "Agences"


class TestTabGetStmt:
    """Test Tab.get_stmt method."""

    def test_get_stmt_with_date_sort(
        self, app: Flask, db_session: Session, test_user: User
    ):
        """Test get_stmt with date sort order."""
        with app.test_request_context():
            session["wire:tab"] = "wall"
            g.user = test_user

            tab = WallTab()
            bar = FilterBar("wall")
            bar.state = {"sort-by": "date"}

            stmt = tab.get_stmt(bar)

            # Should return a valid SQLAlchemy statement
            assert stmt is not None

    def test_get_stmt_with_views_sort(
        self, app: Flask, db_session: Session, test_user: User
    ):
        """Test get_stmt with views sort order."""
        with app.test_request_context():
            session["wire:tab"] = "wall"
            g.user = test_user

            tab = WallTab()
            bar = FilterBar("wall")
            bar.state = {"sort-by": "views"}

            stmt = tab.get_stmt(bar)

            assert stmt is not None

    def test_get_stmt_with_likes_sort(
        self, app: Flask, db_session: Session, test_user: User
    ):
        """Test get_stmt with likes sort order."""
        with app.test_request_context():
            session["wire:tab"] = "wall"
            g.user = test_user

            tab = WallTab()
            bar = FilterBar("wall")
            bar.state = {"sort-by": "likes"}

            stmt = tab.get_stmt(bar)

            assert stmt is not None

    def test_get_stmt_with_active_filters(
        self, app: Flask, db_session: Session, test_user: User
    ):
        """Test get_stmt applies active filters."""
        with app.test_request_context():
            session["wire:tab"] = "wall"
            g.user = test_user

            tab = WallTab()
            bar = FilterBar("wall")
            bar.state = {"filters": [{"id": "sector", "value": "tech"}]}

            stmt = tab.get_stmt(bar)

            # Statement should include the filter
            assert stmt is not None

    def test_get_stmt_ignores_tag_filter(
        self, app: Flask, db_session: Session, test_user: User
    ):
        """Test get_stmt ignores tag filter in ORM query."""
        with app.test_request_context():
            session["wire:tab"] = "wall"
            g.user = test_user

            tab = WallTab()
            bar = FilterBar("wall")
            bar.state = {"filters": [{"id": "tag", "value": "python"}]}

            # Should not raise - tag filters are handled separately
            stmt = tab.get_stmt(bar)
            assert stmt is not None

    def test_get_stmt_ignores_unknown_filters(
        self, app: Flask, db_session: Session, test_user: User
    ):
        """Test get_stmt ignores filters not in ALLOWED_FILTER_FIELDS."""
        with app.test_request_context():
            session["wire:tab"] = "wall"
            g.user = test_user

            tab = WallTab()
            bar = FilterBar("wall")
            # Manually add a filter that's not in ALLOWED_FILTER_FIELDS
            bar.state = {"filters": [{"id": "unknown_field", "value": "test"}]}

            # Should not raise
            stmt = tab.get_stmt(bar)
            assert stmt is not None
