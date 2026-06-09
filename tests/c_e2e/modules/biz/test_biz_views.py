# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for biz views (convention-driven navigation)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import g, render_template

from app.models.auth import User
from app.modules.biz.models import EditorialProduct
from app.modules.biz.views.home import _get_filters

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user for biz tests."""
    user = User(email="biz_views_test@example.com")
    user.photo = b""
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(app: Flask, test_user: User) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = getattr(test_user, "fs_uniquifier", str(test_user.id))

    return client


class TestBizItemOrglessSeller:
    """Regression (audit 2026-05-15, C2): a marketplace item whose
    seller has no KYC profile must render.

    `biz-item--main.j2:111` did `{{ seller.profile.presentation }}`
    unguarded. `User.profile` is nullable (`auth.py:210` itself does
    `if self.profile is None`), so a seller without a completed KYC
    profile raised `UndefinedError: 'None' has no attribute
    'presentation'` under StrictUndefined and 500'd the item page.
    Line 82 of the same template already used the null-safe
    `seller.organisation_name` — `.profile` was the missed chain.

    Rendered via `flask.render_template` (provides the object-aware
    `url_for` context processor the template needs — it's NOT the
    Jinja global, so a bare `get_template().render()` breaks). The
    c_e2e fake-auth client only 302/401s on `/biz/<id>`, so the route
    path is unreachable here (same harness limit as the events
    orgless test). `g.user` is forced to `None` so the global
    `inject_nav` context processor builds the menu without
    role-gating — deterministic regardless of any leftover detached
    `g.user` from prior full-suite tests (the flake this replaces).
    """

    def test_item_main_renders_with_profileless_seller(
        self, app: Flask, db_session: Session, test_user: User
    ) -> None:
        seller = User(
            email="profileless_seller@example.com",
            first_name="Pro",
            last_name="Fileless",
        )
        seller.photo = b""
        db_session.add(seller)
        db_session.flush()
        assert seller.profile is None  # the missed `.profile` chain

        item = EditorialProduct(
            owner=seller,
            title="Profileless seller product",
            description="desc",
        )
        db_session.add(item)
        db_session.flush()

        with app.test_request_context():
            g.user = None  # nav skips role checks → no detached lazy-load
            html = render_template("pages/biz-item--main.j2", item=item)

        assert "Profileless seller product" in html


class TestBizHomeView:
    """Test biz home (marketplace) view."""

    def test_biz_home_accessible(self, authenticated_client: FlaskClient):
        """Test biz home page is accessible."""
        response = authenticated_client.get("/biz/")
        assert response.status_code in (200, 302)

    def test_biz_home_with_tab(self, authenticated_client: FlaskClient):
        """Test biz home page with tab parameter."""
        response = authenticated_client.get("/biz/?current_tab=subscriptions")
        assert response.status_code in (200, 302)

    def test_journalism_filters_visible_on_journalism_view(self, app: Flask):
        """Ticket #0202 — the journalism-specific filters appear only
        when `current_tab=missions` AND `category=journalisme`. We
        exercise the filter helper directly (the full home view goes
        through the same code path) to keep the test independent of
        the auth fixture's wiring."""
        with app.test_request_context(
            "/biz/?current_tab=missions&category=journalisme"
        ):
            ids_with = [f["id"] for f in _get_filters()]

        with app.test_request_context("/biz/?current_tab=missions"):
            ids_without = [f["id"] for f in _get_filters()]

        # Without category=journalisme, only the generic filters are
        # present.
        for fid in ("metiers_journalisme", "competences_journalisme"):
            assert fid not in ids_without

        # With category=journalisme, the spec'd filters land.
        for fid in (
            "metiers_journalisme",
            "types_entreprises_presse_medias",
            "competences_journalisme",
            "modes_remuneration",
            "work_mode",
            "budget_min",
            "budget_max",
            "deadline",
            "pays",
            "code_postal_ville",
        ):
            assert fid in ids_with, f"journalism filter {fid!r} missing"


class TestBizPurchasesView:
    """Test biz purchases view."""

    def test_purchases_accessible(self, authenticated_client: FlaskClient):
        """Test purchases page is accessible."""
        response = authenticated_client.get("/biz/purchases/")
        assert response.status_code in (200, 302)


class TestNavigationIntegration:
    """Test navigation system integration with biz views."""

    def test_nav_tree_includes_biz_section(self, app):
        """Test that nav tree includes biz section."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "biz" in nav_tree._sections
            section = nav_tree._sections["biz"]
            assert section.label == "Marketplace"

    def test_nav_tree_includes_biz_page(self, app):
        """Test that nav tree includes biz home page."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "biz.biz" in nav_tree._nodes

    def test_nav_tree_includes_purchases_page(self, app):
        """Test that nav tree includes purchases page."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "biz.purchases" in nav_tree._nodes

    def test_nav_tree_includes_biz_item_page(self, app):
        """Test that nav tree includes biz item page."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            assert "biz.biz_item" in nav_tree._nodes

    def test_breadcrumbs_for_biz_home(self, app):
        """Test breadcrumbs generation for biz home."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("biz.biz", {})
            assert len(crumbs) >= 1
            assert crumbs[-1].current is True

    def test_breadcrumbs_for_purchases(self, app):
        """Test breadcrumbs generation for purchases page."""
        nav_tree = app.extensions["nav_tree"]

        with app.app_context():
            nav_tree.build(app)
            crumbs = nav_tree.build_breadcrumbs("biz.purchases", {})
            assert len(crumbs) >= 2  # Home + Purchases
            assert crumbs[-1].current is True
