# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Articles WIP views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus
from app.modules.bw.bw_activation.models.business_wall import (
    BusinessWall,
    BWStatus,
)
from app.modules.wip.models.newsroom.article import Article
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User
    from app.models.organisation import Organisation


@pytest.fixture
def test_article(
    db_session: Session, test_org: Organisation, test_user: User
) -> Article:
    """Create a test article in DRAFT status."""
    article = Article(owner=test_user, media=test_org)
    article.titre = "Test Article Title"
    article.contenu = "Test article content"
    article.date_parution_prevue = arrow.get("2025-12-01").datetime
    article.commanditaire_id = test_user.id
    article.status = PublicationStatus.DRAFT
    db_session.add(article)
    db_session.flush()
    return article


@pytest.fixture
def published_article(
    db_session: Session, test_org: Organisation, test_user: User
) -> Article:
    """Create a test article in PUBLIC status."""
    article = Article(owner=test_user, media=test_org)
    article.titre = "Published Article"
    article.contenu = "Published article content"
    article.date_parution_prevue = arrow.get("2025-12-01").datetime
    article.commanditaire_id = test_user.id
    article.status = PublicationStatus.DRAFT
    article.publish(publisher_id=test_org.id)
    db_session.add(article)
    db_session.flush()
    return article


class TestArticlesCreateValidation:
    """Regression : a create POST that omits the required fields (dates,
    genre/section/topic/sector selects) must re-render the form with
    errors, NOT 500.

    The article view overrides `post` with `_ARTICLE_MODIFIER_TEMPLATE`,
    whose step-nav needs `article` in the context (like get/edit set) and
    a persisted model. On a failed *create* the model is a fresh, unsaved
    Article (id is None), so the error path used to raise
    `UndefinedError: 'article' is undefined`."""

    def test_create_without_required_fields_rejects_cleanly(
        self, logged_in_client: FlaskClient
    ):
        response = logged_in_client.post(
            "/wip/articles/",
            data={
                "_action": "save",
                "titre": "no-date-article",
                "chapo": "Chapô",
                "contenu": "<p>Test</p>",
                "copyright": "all-rights-reserved",
            },
            follow_redirects=False,
        )
        # Form rejected and re-rendered (not a 302 save, not a 500).
        assert response.status_code == 200
        assert b"This field is required" in response.data


class TestArticlesIndex:
    """Tests for the articles index view."""

    def test_index_loads_successfully(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test that index page loads successfully for authenticated user."""
        url = url_for("ArticlesWipView:index")
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_index_actions_column_shows_menu_header_and_styled_button(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Erick (2026-05-21) : le menu d'actions (trois points) est
        difficile à repérer pour les non-techs. Ajustement léger : un
        en-tête « Menu » au-dessus de la colonne, et un bouton coloré
        avec la palette « primary » (celle du bouton « +New ») au lieu
        du gris discret."""
        url = url_for("ArticlesWipView:index")
        response = logged_in_client.get(url)
        assert response.status_code == 200
        html = response.data.decode()
        # Header label
        assert (
            ">Menu</th>" in html
            or ">\n      Menu" in html.replace("\n        ", "\n      ")
            or "Menu</th>" in html
        ), "L'en-tête de la colonne actions doit afficher « Menu »"
        # Button color aligned with the +New (primary) palette
        assert "text-primary-700" in html, (
            "Le bouton trois-points doit utiliser la palette `primary`"
        )

    def test_index_no_rights_reminder_without_media_bw(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Without an active media BW, the rights-policy banner is hidden."""
        url = url_for("ArticlesWipView:index")
        response = logged_in_client.get(url)
        assert response.status_code == 200
        assert "Gérer les modalités" not in response.data.decode()

    def test_index_shows_rights_reminder_for_media_bw(
        self,
        app,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
        test_article: Article,
    ):
        """A user whose active BW is `media` sees a link to rights-policy."""
        bw = BusinessWall(
            bw_type="media",
            status=BWStatus.ACTIVE.value,
            owner_id=test_user.id,
            payer_id=test_user.id,
            organisation_id=test_org.id,
            name="Test Media BW",
        )
        db_session.add(bw)
        db_session.commit()
        test_org.bw_id = bw.id
        test_org.bw_active = "media"
        db_session.commit()

        client = make_authenticated_client(app, test_user)
        url = url_for("ArticlesWipView:index")
        response = client.get(url)
        assert response.status_code == 200
        body = response.data.decode()
        assert "Gérer les modalités" in body
        assert "/BW/rights-policy" in body


class TestArticlesPublish:
    """Tests for the article publish workflow."""

    def test_publish_article_success(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_article: Article,
    ):
        """Test successfully publishing a draft article."""
        url = url_for("ArticlesWipView:publish", id=test_article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect to index after successful publish
        assert response.status_code == 302

        # Article should now be PUBLIC
        assert test_article.status == PublicationStatus.PUBLIC

    def test_publish_article_without_titre(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ):
        """Test that publishing fails without titre."""
        # Create article without titre
        article = Article(owner=test_user, media=test_org)
        article.titre = ""  # Empty titre
        article.contenu = "Some content"
        article.date_parution_prevue = arrow.get("2025-12-01").datetime
        article.commanditaire_id = test_user.id
        article.status = PublicationStatus.DRAFT
        db_session.add(article)
        db_session.flush()

        url = url_for("ArticlesWipView:publish", id=article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect back to edit with error
        assert response.status_code == 302

        # Article should still be in DRAFT status
        assert article.status == PublicationStatus.DRAFT

    def test_publish_article_without_contenu(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ):
        """Test that publishing fails without contenu."""
        # Create article without contenu
        article = Article(owner=test_user, media=test_org)
        article.titre = "Test Title"
        article.contenu = ""  # Empty contenu
        article.date_parution_prevue = arrow.get("2025-12-01").datetime
        article.commanditaire_id = test_user.id
        article.status = PublicationStatus.DRAFT
        db_session.add(article)
        db_session.flush()

        url = url_for("ArticlesWipView:publish", id=article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect back to edit with error
        assert response.status_code == 302

        # Article should still be in DRAFT status
        assert article.status == PublicationStatus.DRAFT

    def test_publish_already_published_article(
        self,
        logged_in_client: FlaskClient,
        published_article: Article,
    ):
        """Test that publishing an already published article fails."""
        url = url_for("ArticlesWipView:publish", id=published_article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect with error
        assert response.status_code == 302

        # Article should still be PUBLIC
        assert published_article.status == PublicationStatus.PUBLIC


class TestArticlesUnpublish:
    """Tests for the article unpublish workflow."""

    def test_unpublish_article_success(
        self,
        logged_in_client: FlaskClient,
        published_article: Article,
    ):
        """Test successfully unpublishing a published article."""
        url = url_for("ArticlesWipView:unpublish", id=published_article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect to index after success
        assert response.status_code == 302

        # Article should now be DRAFT
        assert published_article.status == PublicationStatus.DRAFT

    def test_unpublish_draft_article(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test that unpublishing a draft article fails."""
        url = url_for("ArticlesWipView:unpublish", id=test_article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect with error
        assert response.status_code == 302

        # Article should still be DRAFT
        assert test_article.status == PublicationStatus.DRAFT


class TestArticlesCRUD:
    """Tests for basic CRUD operations on articles."""

    def test_get_article_detail(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test viewing article detail."""
        url = url_for("ArticlesWipView:get", id=test_article.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_edit_article_form(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test loading article edit form."""
        url = url_for("ArticlesWipView:edit", id=test_article.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_create_article_form(self, logged_in_client: FlaskClient):
        """Test loading article creation form."""
        url = url_for("ArticlesWipView:new")
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_voir_step_nav_links_to_list_and_modifier(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Ticket #0154 (Erick, 2026-05-22) — extend the step nav
        from Avis d'enquête to Articles : on « Voir », surface
        a « Retourner à la liste » link and a « Étape suivante :
        Modifier » button."""
        url = url_for("ArticlesWipView:get", id=test_article.id)
        body = logged_in_client.get(url).data.decode()
        assert "Retourner à la liste" in body, (
            "voir page must surface a return-to-list link (#0154)"
        )
        assert "Étape suivante" in body, (
            "voir page must surface the « Étape suivante » button (#0154)"
        )
        assert "Modifier" in body, (
            "voir's next-step button must point to « Modifier » (#0154)"
        )

    def test_modifier_step_nav_links_to_list_and_back_to_voir(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Ticket #0154 — on « Modifier », surface a « Retourner à
        la liste » link and a « Étape précédente : Voir » link."""
        url = url_for("ArticlesWipView:edit", id=test_article.id)
        body = logged_in_client.get(url).data.decode()
        assert "Retourner à la liste" in body
        assert "Étape précédente" in body
        # The back-step points at the « Voir » action.
        assert f"/wip/articles/{test_article.id}" in body


class TestArticlesDelete:
    """Tests for deleting articles."""

    def test_delete_own_article(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_article: Article,
    ):
        """Test deleting own article redirects."""
        url = url_for("ArticlesWipView:delete", id=test_article.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302

    def test_delete_article_sets_deleted_at(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_article: Article,
    ):
        """Test delete sets deleted_at timestamp."""
        url = url_for("ArticlesWipView:delete", id=test_article.id)
        logged_in_client.get(url, follow_redirects=False)
        db_session.refresh(test_article)
        assert test_article.deleted_at is not None


class TestArticlesHtmx:
    """Tests for HTMX table views."""

    def test_htmx_table_loads(
        self,
        logged_in_client: FlaskClient,
        test_article: Article,
    ):
        """Test HTMX table endpoint returns HTML fragment."""
        url = url_for("ArticlesWipView:htmx")
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestArticlesValidation:
    """Tests for article validation logic."""

    def test_article_status_properties(self, test_article: Article):
        """Test article status query properties."""
        # Draft article
        assert test_article.is_draft is True
        assert test_article.is_public is False

        # Publish it
        test_article.publish()
        assert test_article.is_draft is False
        assert test_article.is_public is True

        # Unpublish it
        test_article.unpublish()
        assert test_article.is_draft is True
        assert test_article.is_public is False

    def test_article_can_publish_logic(self, test_article: Article):
        """Test can_publish business logic."""
        # Draft article can be published
        assert test_article.can_publish() is True

        # Published article cannot be published again
        test_article.publish()
        assert test_article.can_publish() is False

    def test_article_can_unpublish_logic(self, test_article: Article):
        """Test can_unpublish business logic."""
        # Draft article cannot be unpublished
        assert test_article.can_unpublish() is False

        # Published article can be unpublished
        test_article.publish()
        assert test_article.can_unpublish() is True
