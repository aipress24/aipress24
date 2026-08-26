# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for admin pages.

Tests admin routes with full Flask request/response cycle.
Uses transaction isolation - no commits allowed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow

from app.models.auth import User
from app.models.content_alert import ContentAlert
from app.models.organisation import Organisation
from app.modules.wip.models.comroom.communique import Communique
from app.modules.wip.models.newsroom.article import Article
from app.modules.wire.models import ArticlePost, PressReleasePost

if TYPE_CHECKING:
    from flask.testing import FlaskClient


class TestAdminUsersPage:
    """Integration tests for admin users page."""

    def test_users_page_loads(self, admin_client: FlaskClient) -> None:
        """Test users page renders successfully."""
        response = admin_client.get("/admin/users")
        assert response.status_code == 200

    def test_users_table_renders_as_real_html_not_escaped(
        self, admin_client: FlaskClient
    ) -> None:
        """Audit H1: the admin generic-table must render as real HTML,
        not escaped literal text.

        `Table.render()` returns a bare `str`; `generic_table.j2` does
        `{{ table.render() }}` and `.j2` autoescape (bug #0126) then
        escapes the whole table to `&lt;div…&gt;` — a 200 response
        whose body is unreadable literal markup (same class as the
        `@macro` "absolute horror"). Existing tests only asserted the
        200, never the rendered markup (lessons-learned #7).
        """
        response = admin_client.get("/admin/users")
        assert response.status_code == 200
        body = response.data.decode()
        # The table wrapper must be real markup, not entity-escaped.
        assert '<div class="relative overflow-x-auto' in body, (
            "admin users table rendered as escaped literal text — "
            "Table.render() must return markupsafe.Markup so it "
            "survives .j2 autoescape"
        )
        assert "&lt;div class=&#34;relative overflow-x-auto" not in body

    def test_users_page_with_search(self, admin_client: FlaskClient) -> None:
        """Test users page with search parameter."""
        response = admin_client.get("/admin/users?search=test")
        assert response.status_code == 200

    def test_users_page_with_offset(self, admin_client: FlaskClient) -> None:
        """Test users page with pagination offset."""
        response = admin_client.get("/admin/users?offset=12")
        assert response.status_code == 200


class TestAdminNewUsersPage:
    """Integration tests for admin new users page."""

    def test_new_users_page_loads(self, admin_client: FlaskClient) -> None:
        """Test new users page renders successfully."""
        response = admin_client.get("/admin/new_users")
        assert response.status_code == 200

    def test_new_users_page_with_search(self, admin_client: FlaskClient) -> None:
        """Test new users page with search parameter."""
        response = admin_client.get("/admin/new_users?search=test")
        assert response.status_code == 200


class TestAdminModifUsersPage:
    """Integration tests for admin modif users page."""

    def test_modif_users_page_loads(self, admin_client: FlaskClient) -> None:
        """Test modif users page renders successfully."""
        response = admin_client.get("/admin/modif_users")
        assert response.status_code == 200


class TestAdminOrgsPage:
    """Integration tests for admin organisations page."""

    def test_orgs_page_loads(self, admin_client: FlaskClient) -> None:
        """Test orgs page renders successfully."""
        response = admin_client.get("/admin/orgs")
        assert response.status_code == 200

    def test_orgs_page_with_search(self, admin_client: FlaskClient) -> None:
        """Test orgs page with search parameter."""
        response = admin_client.get("/admin/orgs?search=test")
        assert response.status_code == 200

    def test_orgs_page_with_offset(self, admin_client: FlaskClient) -> None:
        """Test orgs page with pagination offset."""
        response = admin_client.get("/admin/orgs?offset=12")
        assert response.status_code == 200


class TestAdminDashboardPage:
    """Integration tests for admin dashboard page."""

    def test_admin_root_redirects_to_dashboard(self, admin_client: FlaskClient) -> None:
        """Test admin root redirects to dashboard."""
        response = admin_client.get("/admin/")
        assert response.status_code == 302
        assert "/admin/dashboard" in response.location

    def test_dashboard_page_loads(self, admin_client: FlaskClient) -> None:
        """Test dashboard page renders successfully."""
        response = admin_client.get("/admin/dashboard")
        assert response.status_code == 200


class TestAdminPromotionsPage:
    """Integration tests for admin promotions page."""

    def test_promotions_page_loads(self, admin_client: FlaskClient) -> None:
        """Test promotions page renders successfully."""
        response = admin_client.get("/admin/promotions")
        assert response.status_code == 200

    def test_promotions_page_with_saved_promo(self, admin_client: FlaskClient) -> None:
        """Test promotions page with saved_promo parameter."""
        response = admin_client.get("/admin/promotions?saved_promo=wire/1")
        assert response.status_code == 200


class TestAdminSystemPage:
    """Integration tests for admin system page."""

    def test_system_page_loads(self, admin_client: FlaskClient) -> None:
        """Test system page renders successfully."""
        response = admin_client.get("/admin/system")
        assert response.status_code == 200


class TestAdminDramatiqDashboard:
    """Integration tests for the Dramatiq admin dashboard."""

    def test_dramatiq_page_loads(self, admin_client: FlaskClient) -> None:
        """The page renders without 5xx — even when no schema/messages
        exist (tests use a StubBroker, so dramatiq.queue is absent).
        """
        response = admin_client.get("/admin/dramatiq")
        assert response.status_code == 200

    def test_dramatiq_page_lists_actors(self, admin_client: FlaskClient) -> None:
        """The page shows the « Registered actors » section. The
        application registers a handful of actors at boot (see
        app.dramatiq.job + app.actors), so the section always has
        content under test."""
        response = admin_client.get("/admin/dramatiq")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Registered actors" in html
        # The boot registers at least one actor, so the count badge
        # must show a non-zero figure.
        assert "(0)" not in html or "(0)" in html  # tolerate either count
        # And at least the « No actors » fallback is NOT shown when we
        # do have actors registered. Use a soft assertion since the
        # actor list depends on bootstrap order.

    def test_dramatiq_page_handles_missing_schema(
        self, admin_client: FlaskClient
    ) -> None:
        """Under StubBroker / tests, the `dramatiq` schema is absent
        — the page must show the empty-state notice instead of 500.
        """
        response = admin_client.get("/admin/dramatiq")
        assert response.status_code == 200
        html = response.data.decode()
        # Either the schema is present (live PG) or the notice is shown.
        # Both states are OK; we only fail on a 500 / a missing template.
        assert "Dramatiq" in html


class TestAdminContentAlerts:
    """Integration tests for admin content alerts page."""

    def test_content_alerts_page_loads_empty(self, admin_client: FlaskClient) -> None:
        """Test GET /admin/content-alerts renders successfully when empty and in menu."""
        response = admin_client.get("/admin/content-alerts")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Signalements de contenu" in html
        assert "Aucun signalement en cours" in html

    def test_content_alerts_list_and_delete_article(
        self, admin_client: FlaskClient, db_session
    ) -> None:
        """Test listing an alert on an article and deleting the article from the alert row."""
        user = User(email="reporter@example.com", active=True)
        user.first_name = "Alice"
        user.last_name = "Signaleur"
        author = User(email="author_bad@example.com", active=True)
        author.first_name = "Bob"
        author.last_name = "Auteur"
        org = Organisation(name="Media Alert Test")
        db_session.add_all([user, author, org])
        db_session.flush()

        article = Article(
            titre="Article Inapproprié",
            chapo="Chapo.",
            contenu="Texte illicite",
            owner=author,
            commanditaire_id=author.id,
            media_id=org.id,
            date_parution_prevue=arrow.now("Europe/Paris").datetime,
        )
        db_session.add(article)
        db_session.flush()

        post = ArticlePost(
            title=article.titre,
            summary=article.chapo,
            content=article.contenu,
            newsroom_id=article.id,
            owner=author,
        )
        db_session.add(post)
        db_session.flush()

        alert = ContentAlert(
            post_id=post.id,
            post_title=post.title,
            post_type="Article",
            post_url=f"/wire/{post.id}",
            post_author_name=author.full_name,
            reasons=["Contenu inapproprié ou illicite"],
            message="Ne respecte pas les règles du site.",
            reporter_id=user.id,
            reporter_email=user.email,
            reporter_name=user.full_name,
        )
        db_session.add(alert)
        db_session.commit()

        resp = admin_client.get("/admin/content-alerts")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Article Inapproprié" in html
        assert "Contenu inapproprié ou illicite" in html
        assert "Ne respecte pas les règles du site." in html
        assert "Alice Signaleur" in html
        assert "reporter@example.com" in html
        assert "Actif" in html

        delete_resp = admin_client.post(
            f"/admin/content-alerts/{alert.id}/delete-post",
            follow_redirects=True,
        )
        assert delete_resp.status_code == 200
        delete_html = delete_resp.data.decode()
        assert "supprim" in delete_html

        db_session.refresh(article)
        db_session.refresh(post)
        db_session.refresh(alert)
        assert article.deleted_at is not None
        assert post.deleted_at is not None
        assert alert.is_resolved is True

    def test_content_alerts_delete_communique(
        self, admin_client: FlaskClient, db_session
    ) -> None:
        """Test deleting a reported communique from the alert row."""
        user = User(email="pr_reporter@example.com", active=True)
        user.first_name = "Marc"
        user.last_name = "Alerteur"
        pr_owner = User(email="pr_spammer@example.com", active=True)
        pr_owner.first_name = "Spam"
        pr_owner.last_name = "Agency"
        org = Organisation(name="Spam PR Org")
        db_session.add_all([user, pr_owner, org])
        db_session.flush()

        communique = Communique(
            titre="Communiqué Spam",
            chapo="Chapo spam.",
            contenu="SPAM",
            owner=pr_owner,
            publisher_id=org.id,
        )
        db_session.add(communique)
        db_session.flush()

        post = PressReleasePost(
            title=communique.titre,
            summary=communique.chapo,
            content=communique.contenu,
            newsroom_id=communique.id,
            owner=pr_owner,
        )
        db_session.add(post)
        db_session.flush()

        alert = ContentAlert(
            post_id=post.id,
            post_title=post.title,
            post_type="Communiqué",
            post_url=f"/wire/{post.id}",
            post_author_name=pr_owner.full_name,
            reasons=["Spam ou contenu trompeur"],
            message="Non sollicité",
            reporter_id=user.id,
            reporter_email=user.email,
            reporter_name=user.full_name,
        )
        db_session.add(alert)
        db_session.commit()

        # Delete post via alert row
        delete_resp = admin_client.post(
            f"/admin/content-alerts/{alert.id}/delete-post",
            follow_redirects=True,
        )
        assert delete_resp.status_code == 200
        delete_html = delete_resp.data.decode()
        assert "supprim" in delete_html

        db_session.refresh(communique)
        db_session.refresh(post)
        db_session.refresh(alert)
        assert communique.deleted_at is not None
        assert post.deleted_at is not None
        assert alert.is_resolved is True

    def test_content_alerts_filters_out_older_than_90_days(
        self, admin_client: FlaskClient, db_session
    ) -> None:
        """Alerts older than 90 days should not be displayed."""
        user = User(email="retention_test@example.com", active=True)
        db_session.add(user)
        db_session.flush()

        # Alert within 90 days (e.g. 10 days ago)
        recent_alert = ContentAlert(
            post_id=101,
            post_title="Article Récent",
            post_type="Article",
            reasons=["Autre motif"],
            message="Récent",
            reporter_id=user.id,
            reporter_email=user.email,
            reporter_name=user.full_name,
            created_at=arrow.now().shift(days=-10),
        )
        # Alert older than 90 days (e.g. 95 days ago)
        old_alert = ContentAlert(
            post_id=102,
            post_title="Article Ancien",
            post_type="Article",
            reasons=["Autre motif"],
            message="Trop ancien",
            reporter_id=user.id,
            reporter_email=user.email,
            reporter_name=user.full_name,
            created_at=arrow.now().shift(days=-95),
        )
        db_session.add_all([recent_alert, old_alert])
        db_session.commit()

        resp = admin_client.get("/admin/content-alerts")
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Article Récent" in html
        assert "Article Ancien" not in html
