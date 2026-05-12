# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""End-to-end tests for the /search/ page.

These hit the Flask test client (not a real browser), so they cover
the view + template + engine wiring without needing a live server.
Indexing is bypassed by injecting a RAM-backed ``SearchEngine`` into
the SVCS container — production indexing is exercised in
``tests/b_integration/modules/search/``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
import svcs.flask
from wesh.backends.filedb.filestore import RamStorage

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.modules.search.engine import SearchEngine
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from collections.abc import Iterator

    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user(db_session: Session) -> User:
    role = Role(
        name=RoleEnum.PRESS_MEDIA.name,
        description=RoleEnum.PRESS_MEDIA.value,
    )
    db_session.add(role)
    db_session.flush()

    user = User(email="search_views_test@example.com")
    user.photo = b""
    user.active = True
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    return make_authenticated_client(app, test_user)


@pytest.fixture
def test_engine(app: Flask) -> Iterator[SearchEngine]:
    """Inject a RAM-backed engine into the SVCS container for the
    duration of the test.
    """
    engine = SearchEngine(RamStorage())
    previous = svcs.flask.overwrite_value(SearchEngine, engine)
    try:
        yield engine
    finally:
        if previous is not None:
            svcs.flask.overwrite_value(SearchEngine, previous)


class TestSearchView:
    def test_empty_query_renders_landing(
        self, authenticated_client: FlaskClient, test_engine: SearchEngine
    ):
        response = authenticated_client.get("/search/")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Tapez un mot-clé" in body

    def test_query_with_no_hits_renders_no_results(
        self, authenticated_client: FlaskClient, test_engine: SearchEngine
    ):
        response = authenticated_client.get("/search/?qs=nonexistent")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Aucun résultat" in body

    def test_query_with_hit_shows_title_and_url(
        self, authenticated_client: FlaskClient, test_engine: SearchEngine
    ):
        test_engine.upsert(
            {
                "type": "article",
                "id": "article:1",
                "title": "Python at scale",
                "text": "long form piece on Python in production",
                "summary": "Production Python.",
                "url": "/wire/abc",
                "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
                "tags": "",
            }
        )

        response = authenticated_client.get("/search/?qs=Python")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Python at scale" in body
        assert "/wire/abc" in body

    def test_type_filter_excludes_other_types(
        self, authenticated_client: FlaskClient, test_engine: SearchEngine
    ):
        test_engine.upsert(
            {
                "type": "article",
                "id": "article:10",
                "title": "Article hit",
                "text": "article body matching topic",
                "summary": "",
                "url": "/a/10",
                "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
                "tags": "",
            }
        )
        test_engine.upsert(
            {
                "type": "event",
                "id": "event:20",
                "title": "Event hit",
                "text": "event body matching topic",
                "summary": "",
                "url": "/e/20",
                "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
                "tags": "",
            }
        )

        response = authenticated_client.get("/search/?qs=topic&filter=articles")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Article hit" in body
        assert "Event hit" not in body

    @pytest.mark.parametrize(
        "filter_name", ["all", "articles", "press-releases", "events"]
    )
    def test_all_filters_render_without_5xx(
        self,
        authenticated_client: FlaskClient,
        test_engine: SearchEngine,
        filter_name: str,
    ):
        response = authenticated_client.get(f"/search/?qs=foo&filter={filter_name}")
        assert response.status_code == 200

    def test_unknown_filter_renders_without_error(
        self, authenticated_client: FlaskClient, test_engine: SearchEngine
    ):
        # Unknown filters degrade to "no matching collection" — the
        # page must still render 200, just with no result sets.
        response = authenticated_client.get("/search/?qs=foo&filter=bogus")
        assert response.status_code == 200


class TestNavigationIntegration:
    """Test navigation system integration with search views."""

    def test_nav_tree_includes_search_section(self, app):
        nav_tree = app.extensions["nav_tree"]
        with app.app_context():
            nav_tree.build(app)
            assert "search" in nav_tree._sections
            section = nav_tree._sections["search"]
            assert section.label == "Rechercher"

    def test_nav_tree_includes_search_page(self, app):
        nav_tree = app.extensions["nav_tree"]
        with app.app_context():
            nav_tree.build(app)
            assert "search.search" in nav_tree._nodes

    def test_breadcrumbs_for_search(self, app):
        nav_tree = app.extensions["nav_tree"]
        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("search.search", {})
            assert len(crumbs) >= 1
            assert crumbs[-1].current is True
