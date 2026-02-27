# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for image operations in WIP CRUD views.

Note: Tests that upload images require a running MinIO server.
They are marked with @pytest.mark.requires_storage and will be skipped
if storage is not available.
"""

from __future__ import annotations

import socket
from io import BytesIO
from typing import TYPE_CHECKING

import arrow
import pytest

from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.newsroom.article import Article


def is_minio_available() -> bool:
    """Check if MinIO server is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", 9000))
        sock.close()
        return result == 0
    except OSError:
        return False


requires_storage = pytest.mark.skipif(
    not is_minio_available(),
    reason="MinIO server not available at localhost:9000",
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User
    from app.models.organisation import Organisation


# Minimal valid PNG file (1x1 transparent pixel)
MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def test_article(
    db_session: Session, test_org: Organisation, test_user: User
) -> Article:
    """Create a test article in DRAFT status."""
    article = Article(owner=test_user, media=test_org)
    article.titre = "Test Article for Images"
    article.contenu = "Test article content"
    article.date_parution_prevue = arrow.get("2025-12-01").datetime
    article.commanditaire_id = test_user.id
    article.status = PublicationStatus.DRAFT
    db_session.add(article)
    db_session.commit()
    return article


class TestImagesPage:
    """Tests for the images management page."""

    def test_images_page_loads(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test that images page loads successfully."""
        url = url_for("ArticlesWipView:images", id=test_article.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_images_page_shows_article_title(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test that images page shows article title."""
        url = url_for("ArticlesWipView:images", id=test_article.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200
        assert b"Test Article for Images" in response.data

    def test_images_cancel_redirects_to_index(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test that cancel action redirects to index."""
        url = url_for("ArticlesWipView:images", id=test_article.id)
        response = logged_in_client.post(
            url, data={"_action": "cancel"}, follow_redirects=False
        )
        assert response.status_code == 302


class TestAddImage:
    """Tests for adding images to articles."""

    @requires_storage
    def test_add_image_success(
        self,
        logged_in_client: FlaskClient,
        test_article: Article,
        db_session: Session,
    ):
        """Test successfully adding an image."""
        url = url_for("ArticlesWipView:images", id=test_article.id)
        data = {
            "_action": "add-image",
            "image": (BytesIO(MINIMAL_PNG), "test.png"),
            "caption": "Test caption",
            "copyright": "Test copyright",
        }
        response = logged_in_client.post(
            url,
            data=data,
            content_type="multipart/form-data",
            follow_redirects=False,
        )

        # Should redirect after adding
        assert response.status_code == 302

        # Check image was added
        db_session.refresh(test_article)
        assert len(test_article.images) == 1
        image = test_article.images[0]
        assert image.caption == "Test caption"
        assert image.copyright == "Test copyright"
        assert image.position == 0

    def test_add_image_empty_file_shows_error(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test adding empty image shows error."""
        url = url_for("ArticlesWipView:images", id=test_article.id)
        data = {
            "_action": "add-image",
            "image": (BytesIO(b""), "empty.png"),
        }
        response = logged_in_client.post(
            url,
            data=data,
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Flash message should indicate error
        assert b"vide" in response.data.lower() or b"empty" in response.data.lower()

    @requires_storage
    def test_add_multiple_images_sets_positions(
        self,
        logged_in_client: FlaskClient,
        test_article: Article,
        db_session: Session,
    ):
        """Test that adding multiple images assigns correct positions."""
        url = url_for("ArticlesWipView:images", id=test_article.id)

        # Add first image
        data1 = {
            "_action": "add-image",
            "image": (BytesIO(MINIMAL_PNG), "first.png"),
            "caption": "First image",
        }
        logged_in_client.post(url, data=data1, content_type="multipart/form-data")

        # Add second image
        data2 = {
            "_action": "add-image",
            "image": (BytesIO(MINIMAL_PNG), "second.png"),
            "caption": "Second image",
        }
        logged_in_client.post(url, data=data2, content_type="multipart/form-data")

        db_session.refresh(test_article)
        assert len(test_article.images) == 2

        # Check positions
        images = sorted(test_article.images, key=lambda i: i.position)
        assert images[0].caption == "First image"
        assert images[0].position == 0
        assert images[1].caption == "Second image"
        assert images[1].position == 1


class TestGetImage:
    """Tests for retrieving images."""

    def test_get_image_not_found(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test getting non-existent image returns 404."""
        url = url_for(
            "ArticlesWipView:image", article_id=test_article.id, image_id=99999
        )
        response = logged_in_client.get(url)
        assert response.status_code == 404


class TestDeleteImage:
    """Tests for deleting images."""

    @requires_storage
    def test_delete_image_success(
        self,
        logged_in_client: FlaskClient,
        test_article: Article,
        db_session: Session,
    ):
        """Test successfully deleting an image."""
        # First add an image
        url = url_for("ArticlesWipView:images", id=test_article.id)
        data = {
            "_action": "add-image",
            "image": (BytesIO(MINIMAL_PNG), "test.png"),
            "caption": "To be deleted",
        }
        logged_in_client.post(url, data=data, content_type="multipart/form-data")

        db_session.refresh(test_article)
        image_id = test_article.images[0].id

        # Now delete it
        delete_url = url_for(
            "ArticlesWipView:delete_image",
            article_id=test_article.id,
            image_id=image_id,
        )
        response = logged_in_client.post(delete_url, follow_redirects=False)

        assert response.status_code == 302

        # Check image was deleted
        db_session.refresh(test_article)
        assert len(test_article.images) == 0

    def test_delete_nonexistent_image_returns_404(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test deleting non-existent image returns 404."""
        url = url_for(
            "ArticlesWipView:delete_image",
            article_id=test_article.id,
            image_id=99999,
        )
        response = logged_in_client.post(url)
        assert response.status_code == 404


class TestMoveImage:
    """Tests for reordering images."""

    @requires_storage
    def test_move_image_down(
        self,
        logged_in_client: FlaskClient,
        test_article: Article,
        db_session: Session,
    ):
        """Test moving an image down in order."""
        url = url_for("ArticlesWipView:images", id=test_article.id)

        # Add two images
        data1 = {
            "_action": "add-image",
            "image": (BytesIO(MINIMAL_PNG), "first.png"),
            "caption": "First",
        }
        logged_in_client.post(url, data=data1, content_type="multipart/form-data")

        data2 = {
            "_action": "add-image",
            "image": (BytesIO(MINIMAL_PNG), "second.png"),
            "caption": "Second",
        }
        logged_in_client.post(url, data=data2, content_type="multipart/form-data")

        db_session.refresh(test_article)
        first_image = [i for i in test_article.images if i.position == 0][0]

        # Move first image down
        move_url = url_for(
            "ArticlesWipView:move_image",
            article_id=test_article.id,
            image_id=first_image.id,
        )
        response = logged_in_client.post(
            move_url, data={"direction": "down"}, follow_redirects=False
        )

        assert response.status_code == 302

        # Check positions changed
        db_session.refresh(test_article)
        images = sorted(test_article.images, key=lambda i: i.position)
        assert images[0].caption == "Second"
        assert images[1].caption == "First"

    @requires_storage
    def test_move_image_up(
        self,
        logged_in_client: FlaskClient,
        test_article: Article,
        db_session: Session,
    ):
        """Test moving an image up in order."""
        url = url_for("ArticlesWipView:images", id=test_article.id)

        # Add two images
        data1 = {
            "_action": "add-image",
            "image": (BytesIO(MINIMAL_PNG), "first.png"),
            "caption": "First",
        }
        logged_in_client.post(url, data=data1, content_type="multipart/form-data")

        data2 = {
            "_action": "add-image",
            "image": (BytesIO(MINIMAL_PNG), "second.png"),
            "caption": "Second",
        }
        logged_in_client.post(url, data=data2, content_type="multipart/form-data")

        db_session.refresh(test_article)
        second_image = [i for i in test_article.images if i.position == 1][0]

        # Move second image up
        move_url = url_for(
            "ArticlesWipView:move_image",
            article_id=test_article.id,
            image_id=second_image.id,
        )
        response = logged_in_client.post(
            move_url, data={"direction": "up"}, follow_redirects=False
        )

        assert response.status_code == 302

        # Check positions changed
        db_session.refresh(test_article)
        images = sorted(test_article.images, key=lambda i: i.position)
        assert images[0].caption == "Second"
        assert images[1].caption == "First"

    def test_move_nonexistent_image_returns_404(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test moving non-existent image returns 404."""
        url = url_for(
            "ArticlesWipView:move_image",
            article_id=test_article.id,
            image_id=99999,
        )
        response = logged_in_client.post(url, data={"direction": "up"})
        assert response.status_code == 404
