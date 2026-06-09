# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the search/adapters.py module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.biz.models import (
    EditorialProduct,
    JobOffer,
    MissionOffer,
    ProjectOffer,
)
from app.modules.events.models import EventPost
from app.modules.search.adapters import doc_id, doc_type, is_public, to_doc
from app.modules.wire.models import ArticlePost, PressReleasePost

# ── is_public: pure unit tests (no DB) ─────────────────────────────────


def _stub(cls, *, status, published_at=None, **extra):
    """Build an in-memory model instance for testing ``is_public``.
    Uses the model's regular constructor so SQLAlchemy descriptors stay
    happy, but never adds to the session — this is a detached instance.
    """
    return cls(status=status, published_at=published_at, **extra)


class TestIsPublicArticle:
    def test_draft_is_not_public(self):
        article = _stub(
            ArticlePost,
            status=PublicationStatus.DRAFT,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert is_public(article) is False

    def test_public_with_published_at_is_public(self):
        article = _stub(
            ArticlePost,
            status=PublicationStatus.PUBLIC,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            expires_at=None,
        )
        assert is_public(article) is True

    def test_public_without_published_at_is_not_public(self):
        article = _stub(
            ArticlePost,
            status=PublicationStatus.PUBLIC,
            published_at=None,
            expires_at=None,
        )
        assert is_public(article) is False

    def test_expired_in_past_is_not_public(self):
        past = datetime.now(tz=UTC) - timedelta(days=1)
        article = _stub(
            ArticlePost,
            status=PublicationStatus.PUBLIC,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            expires_at=past,
        )
        assert is_public(article) is False

    def test_expiry_in_future_is_still_public(self):
        future = datetime.now(tz=UTC) + timedelta(days=7)
        article = _stub(
            ArticlePost,
            status=PublicationStatus.PUBLIC,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            expires_at=future,
        )
        assert is_public(article) is True

    @pytest.mark.parametrize(
        "status",
        [
            PublicationStatus.REJECTED,
            PublicationStatus.EXPIRED,
            PublicationStatus.ARCHIVED,
            PublicationStatus.DELETED,
            PublicationStatus.PENDING,
            PublicationStatus.PRIVATE,
        ],
    )
    def test_non_public_statuses_are_not_public(self, status):
        article = _stub(
            ArticlePost,
            status=status,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            expires_at=None,
        )
        assert is_public(article) is False


class TestIsPublicPressRelease:
    def test_public_with_published_at_is_public(self):
        pr = _stub(
            PressReleasePost,
            status=PublicationStatus.PUBLIC,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            expires_at=None,
        )
        assert is_public(pr) is True

    def test_draft_is_not_public(self):
        pr = _stub(PressReleasePost, status=PublicationStatus.DRAFT)
        assert is_public(pr) is False


class TestIsPublicEvent:
    def test_event_uses_expired_at_not_expires_at(self):
        """EventPost's expiry attribute is ``expired_at`` (Publishable
        mixin), not ``expires_at`` (Post). Verify the adapter reads the
        right one.
        """
        past = datetime.now(tz=UTC) - timedelta(days=1)
        event = _stub(
            EventPost,
            status=PublicationStatus.PUBLIC,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            expired_at=past,
        )
        assert is_public(event) is False

    def test_event_public_no_expiry_is_public(self):
        event = _stub(
            EventPost,
            status=PublicationStatus.PUBLIC,
            published_at=datetime(2026, 1, 1, tzinfo=UTC),
            expired_at=None,
        )
        assert is_public(event) is True


class TestIsPublicUnknown:
    def test_unknown_type_raises(self):
        with pytest.raises(TypeError, match="No is_public adapter"):
            is_public(SimpleNamespace(id=1))


# ── to_doc: DB-backed tests ────────────────────────────────────────────


class TestToDocArticle:
    def test_doc_shape(self, db_session, app):
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            article = ArticlePost(
                owner=user,
                title="Python at scale",
                content="A long-form piece on running python services in production.",
                summary="Production python.",
                status=PublicationStatus.PUBLIC,
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            db_session.add(article)
            db_session.flush()

            doc = to_doc(article)

            assert doc["type"] == "article"
            assert doc["id"] == f"article:{article.id}"
            assert doc["title"] == "Python at scale"
            assert doc["summary"] == "Production python."
            assert "Python at scale" in doc["text"]
            assert "running python services" in doc["text"]
            assert "Production python." in doc["text"]
            assert isinstance(doc["url"], str)
            assert doc["url"]  # non-empty
            assert isinstance(doc["timestamp"], datetime)
            assert isinstance(doc["tags"], str)

    def test_doc_with_no_summary_or_content(self, db_session, app):
        with app.test_request_context():
            user = User(email="empty@example.com")
            db_session.add(user)
            db_session.flush()

            article = ArticlePost(owner=user, title="Bare title")
            db_session.add(article)
            db_session.flush()

            doc = to_doc(article)

            assert doc["title"] == "Bare title"
            assert doc["summary"] == ""
            # text should at least carry the title
            assert "Bare title" in doc["text"]
            # No published_at → timestamp is None
            assert doc["timestamp"] is None


class TestToDocPressRelease:
    def test_doc_uses_press_release_type(self, db_session, app):
        with app.test_request_context():
            user = User(email="pr@example.com")
            db_session.add(user)
            db_session.flush()

            pr = PressReleasePost(
                owner=user,
                title="Big announcement",
                content="Body of the press release.",
                summary="TL;DR",
            )
            db_session.add(pr)
            db_session.flush()

            doc = to_doc(pr)

            assert doc["type"] == "press_release"
            assert doc["id"] == f"press_release:{pr.id}"
            assert doc["title"] == "Big announcement"


class TestToDocUnknown:
    def test_unknown_type_raises(self):
        with pytest.raises(TypeError, match="No to_doc adapter"):
            to_doc(SimpleNamespace(id=1, title="x"))


# ── Marketplace ────────────────────────────────────────────────────────


class TestIsPublicMarketplace:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (PublicationStatus.PUBLIC, True),
            (PublicationStatus.DRAFT, False),
            (PublicationStatus.PENDING, False),
            (PublicationStatus.REJECTED, False),
            (PublicationStatus.EXPIRED, False),
            (PublicationStatus.ARCHIVED, False),
            (PublicationStatus.DELETED, False),
        ],
    )
    def test_status_drives_visibility(self, status, expected):
        offer = MissionOffer(status=status)
        assert is_public(offer) is expected

    def test_published_at_is_not_required(self):
        """Unlike articles/events, marketplace doesn't set published_at;
        a PUBLIC status with no timestamp is still indexable."""
        offer = MissionOffer(status=PublicationStatus.PUBLIC, published_at=None)
        assert is_public(offer) is True


class TestDocTypeMarketplace:
    @pytest.mark.parametrize(
        ("cls", "expected_type"),
        [
            (MissionOffer, "mission_offer"),
            (ProjectOffer, "project_offer"),
            (JobOffer, "job_offer"),
            (EditorialProduct, "editorial_product"),
        ],
    )
    def test_doc_type_matches_polymorphic_identity(self, cls, expected_type):
        obj = cls(status=PublicationStatus.PUBLIC)
        assert doc_type(obj) == expected_type
        assert doc_id(obj).startswith(f"{expected_type}:")


class TestToDocMarketplace:
    def test_mission_offer_doc(self, db_session, app):
        with app.test_request_context():
            user = User(email="emitter@example.com")
            db_session.add(user)
            db_session.flush()

            offer = MissionOffer(
                owner=user,
                title="Pige investigation",
                description="Enquête sur la transition écologique.",
                status=PublicationStatus.PUBLIC,
            )
            db_session.add(offer)
            db_session.flush()

            doc = to_doc(offer)

            assert doc["type"] == "mission_offer"
            assert doc["id"] == f"mission_offer:{offer.id}"
            assert doc["title"] == "Pige investigation"
            # description feeds into both summary (no `summary` attr on
            # marketplace) and the text body
            assert doc["summary"] == "Enquête sur la transition écologique."
            assert "Pige investigation" in doc["text"]
            assert "transition écologique" in doc["text"]
            assert isinstance(doc["url"], str)
            assert doc["url"]
            # No published_at set; timestamp tolerated as None
            assert doc["timestamp"] is None

    def test_editorial_product_doc(self, db_session, app):
        with app.test_request_context():
            user = User(email="product@example.com")
            db_session.add(user)
            db_session.flush()

            product = EditorialProduct(
                owner=user,
                title="Reportage exclusif",
                description="Une production éditoriale.",
                status=PublicationStatus.PUBLIC,
            )
            db_session.add(product)
            db_session.flush()

            doc = to_doc(product)

            assert doc["type"] == "editorial_product"
            assert doc["id"] == f"editorial_product:{product.id}"
            assert doc["title"] == "Reportage exclusif"


# ── Group ──────────────────────────────────────────────────────────


# Group adapter tests retirés le 2026-05-21 — les Groupes ne sont plus
# enregistrés dans le moteur de recherche (cf. `search/registry.py`).


# ── User ───────────────────────────────────────────────────────────


class TestIsPublicUser:
    def test_validated_active_user_is_public(self):
        user = User(
            email="x@example.com",
            first_name="Jane",
            last_name="Doe",
            active=True,
            validated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert is_public(user) is True

    def test_inactive_user_is_not_public(self):
        user = User(
            email="x@example.com",
            active=False,
            validated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert is_public(user) is False

    def test_unvalidated_user_is_not_public(self):
        user = User(
            email="x@example.com",
            active=True,
            validated_at=None,
        )
        assert is_public(user) is False

    def test_soft_deleted_user_is_not_public(self):
        user = User(
            email="x@example.com",
            active=True,
            validated_at=datetime(2026, 1, 1, tzinfo=UTC),
            deleted_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
        assert is_public(user) is False


class TestToDocUser:
    def test_doc_shape_without_profile(self, db_session, app):
        with app.test_request_context():
            user = User(
                email="adapter_user@example.com",
                first_name="Jeanne",
                last_name="Martin",
                active=True,
                validated_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            db_session.add(user)
            db_session.flush()

            doc = to_doc(user)

            assert doc["type"] == "user"
            assert doc["id"] == f"user:{user.id}"
            assert doc["title"] == "Jeanne Martin"
            assert "Jeanne" in doc["text"]
            assert "Martin" in doc["text"]
            # No KYC profile attached → summary empty, no crash
            assert doc["summary"] == ""


# ── Organisation ───────────────────────────────────────────────────


class TestIsPublicOrganisation:
    def test_active_org_is_public(self):
        org = Organisation(name="Acme", active=True)
        assert is_public(org) is True

    def test_inactive_org_is_not_public(self):
        org = Organisation(name="Acme", active=False)
        assert is_public(org) is False

    def test_soft_deleted_org_is_not_public(self):
        org = Organisation(
            name="Acme",
            active=True,
            deleted_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert is_public(org) is False


class TestToDocOrganisation:
    def test_doc_shape(self, db_session, app):
        with app.test_request_context():
            org = Organisation(name="Le Quotidien Test", active=True)
            org.bw_name = "Média"
            db_session.add(org)
            db_session.flush()

            doc = to_doc(org)

            assert doc["type"] == "organisation"
            assert doc["id"] == f"organisation:{org.id}"
            assert doc["title"] == "Le Quotidien Test"
            assert "Le Quotidien Test" in doc["text"]
            assert "Média" in doc["text"]
            assert doc["summary"] == "Média"
