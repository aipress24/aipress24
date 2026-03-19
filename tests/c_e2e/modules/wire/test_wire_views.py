# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for wire views - improving coverage for wire.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def press_role(db_session: Session) -> Role:
    """Create a press media role."""
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create test organisation."""
    org = Organisation(name="Test Wire Org")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def test_user(db_session: Session, press_role: Role, test_org: Organisation) -> User:
    """Create test user."""
    user = User(email="wire_views_test@example.com")
    user.first_name = "Wire"
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
    db_session.commit()
    return user


@pytest.fixture
def test_articles(
    db_session: Session, test_user: User, test_org: Organisation
) -> list[ArticlePost]:
    """Create test articles."""
    articles = []
    for i in range(5):
        article = ArticlePost(
            title=f"Test Article {i}",
            content=f"Content for article {i}",
            status=PublicationStatus.PUBLIC,
            publisher=test_org,
            owner=test_user,
            published_at=arrow.now().shift(hours=-i),
            sector="tech",
            topic="news",
        )
        articles.append(article)
        db_session.add(article)

    db_session.commit()
    return articles


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    """Provide authenticated Flask test client."""
    return make_authenticated_client(app, test_user)


class TestWireRedirect:
    """Test wire() redirect view."""

    def test_wire_root_redirects_to_tab(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test /wire/ redirects to active tab."""
        response = authenticated_client.get("/wire/", follow_redirects=False)

        assert response.status_code == 302
        assert "/wire/tab/" in response.location

    def test_wire_root_defaults_to_wall_tab(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test /wire/ defaults to wall tab for new session."""
        response = authenticated_client.get("/wire/", follow_redirects=False)

        assert response.status_code == 302
        # Default tab is 'wall'
        assert "/wire/tab/wall" in response.location


class TestWireTabView:
    """Test WireTabView GET and POST."""

    def test_wire_tab_wall_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test /wire/tab/wall is accessible."""
        response = authenticated_client.get("/wire/tab/wall")
        assert response.status_code == 200

    def test_wire_tab_agencies_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test /wire/tab/agencies is accessible."""
        response = authenticated_client.get("/wire/tab/agencies")
        assert response.status_code == 200

    def test_wire_tab_media_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test /wire/tab/media is accessible."""
        response = authenticated_client.get("/wire/tab/media")
        assert response.status_code == 200

    def test_wire_tab_journalists_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test /wire/tab/journalists is accessible."""
        response = authenticated_client.get("/wire/tab/journalists")
        assert response.status_code == 200

    def test_wire_tab_com_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test /wire/tab/com is accessible."""
        response = authenticated_client.get("/wire/tab/com")
        assert response.status_code == 200

    def test_wire_tab_invalid_returns_404(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test invalid tab returns 404."""
        response = authenticated_client.get("/wire/tab/invalid")
        assert response.status_code == 404

    def test_wire_tab_remembers_last_tab(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test that visiting a tab stores it in session."""
        # Visit agencies tab
        authenticated_client.get("/wire/tab/agencies")

        # Redirect from /wire/ should go to agencies
        response = authenticated_client.get("/wire/", follow_redirects=False)
        assert response.status_code == 302
        assert "/wire/tab/agencies" in response.location

    def test_wire_tab_shows_articles(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_articles: list[ArticlePost],
    ):
        """Test that wire tab shows articles."""
        response = authenticated_client.get("/wire/tab/wall")

        assert response.status_code == 200
        # Check that at least one article title appears
        assert b"Test Article" in response.data


class TestWireTabTagFilter:
    """Test tag filtering via query parameter."""

    def test_tag_query_param_redirects_to_wall(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test ?tag= query parameter redirects to wall tab."""
        response = authenticated_client.get(
            "/wire/tab/agencies?tag=python", follow_redirects=False
        )

        assert response.status_code == 302
        assert "/wire/tab/wall" in response.location


class TestWireTabPost:
    """Test WireTabView POST actions."""

    def test_post_toggle_filter(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test POST with toggle action updates filters."""
        response = authenticated_client.post(
            "/wire/tab/wall",
            data={"action": "toggle", "id": "sector", "value": "tech"},
        )

        assert response.status_code == 200

    def test_post_remove_filter(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test POST with remove action removes filter."""
        # First add a filter
        authenticated_client.post(
            "/wire/tab/wall",
            data={"action": "toggle", "id": "sector", "value": "tech"},
        )

        # Then remove it
        response = authenticated_client.post(
            "/wire/tab/wall",
            data={"action": "remove", "id": "sector", "value": "tech"},
        )

        assert response.status_code == 200

    def test_post_sort_by(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test POST with sort-by action changes sort order."""
        response = authenticated_client.post(
            "/wire/tab/wall",
            data={"action": "sort-by", "value": "views"},
        )

        assert response.status_code == 200

    def test_post_invalid_action_returns_400(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test POST with invalid action returns 400."""
        response = authenticated_client.post(
            "/wire/tab/wall",
            data={"action": "invalid-action"},
        )

        assert response.status_code == 400

    def test_post_invalid_tab_returns_404(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test POST to invalid tab returns 404."""
        response = authenticated_client.post(
            "/wire/tab/invalid",
            data={"action": "toggle", "id": "sector", "value": "tech"},
        )

        assert response.status_code == 404

    def test_post_invalid_filter_id_returns_400(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test POST with unknown filter ID returns 400."""
        response = authenticated_client.post(
            "/wire/tab/wall",
            data={"action": "toggle", "id": "unknown_filter", "value": "test"},
        )

        assert response.status_code == 400
