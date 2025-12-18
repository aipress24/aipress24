# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for biz views (convention-driven navigation)."""

from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.models.auth import User


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for biz tests."""
    user = User(email="biz_views_test@example.com")
    user.photo = b""
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(test_user.fs_uniquifier)
            if hasattr(test_user, "fs_uniquifier")
            else str(test_user.id)
        )

    return client


class TestBizHomeView:
    """Test biz home (marketplace) view."""

    def test_biz_home_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test biz home page is accessible."""
        response = authenticated_client.get("/biz/")
        assert response.status_code in (200, 302)

    def test_biz_home_with_tab(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test biz home page with tab parameter."""
        response = authenticated_client.get("/biz/?current_tab=subscriptions")
        assert response.status_code in (200, 302)


class TestBizPurchasesView:
    """Test biz purchases view."""

    def test_purchases_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test purchases page is accessible."""
        response = authenticated_client.get("/biz/purchases/")
        assert response.status_code in (200, 302)


class TestNavigationIntegration:
    """Test navigation system integration with biz views."""

    def test_nav_tree_includes_biz_section(self, app):
        """Test that nav tree includes biz section."""
        from app.flask.lib.nav import nav_tree

        with app.app_context():
            nav_tree.build(app)
            assert "biz" in nav_tree._sections
            section = nav_tree._sections["biz"]
            assert section.label == "Marketplace"

    def test_nav_tree_includes_biz_page(self, app):
        """Test that nav tree includes biz home page."""
        from app.flask.lib.nav import nav_tree

        with app.app_context():
            nav_tree.build(app)
            assert "biz.biz" in nav_tree._nodes

    def test_nav_tree_includes_purchases_page(self, app):
        """Test that nav tree includes purchases page."""
        from app.flask.lib.nav import nav_tree

        with app.app_context():
            nav_tree.build(app)
            assert "biz.purchases" in nav_tree._nodes

    def test_nav_tree_includes_biz_item_page(self, app):
        """Test that nav tree includes biz item page."""
        from app.flask.lib.nav import nav_tree

        with app.app_context():
            nav_tree.build(app)
            assert "biz.biz_item" in nav_tree._nodes

    def test_breadcrumbs_for_biz_home(self, app):
        """Test breadcrumbs generation for biz home."""
        from app.flask.lib.nav import nav_tree

        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("biz.biz", {})
            assert len(crumbs) >= 1
            assert crumbs[-1].current is True

    def test_breadcrumbs_for_purchases(self, app):
        """Test breadcrumbs generation for purchases page."""
        from app.flask.lib.nav import nav_tree

        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("biz.purchases", {})
            assert len(crumbs) >= 2  # Home + Purchases
            assert crumbs[-1].current is True
