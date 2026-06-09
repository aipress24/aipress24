# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for common/components/post_card.py."""

from __future__ import annotations

from datetime import UTC, datetime

import arrow
import pytest
from flask import render_template_string

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.common.components.post_card import (
    ArticleVM,
    PostCard,
    PressReleaseVM,
    UserVM,
)
from app.modules.wip.models.comroom import Communique
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PressReleasePost,
    PurchaseProduct,
    PurchaseStatus,
)


class TestPostCard:
    """Test PostCard component."""

    def test_get_post_with_article(self, db_session, app):
        """Test get_post returns ArticleVM for ArticlePost."""
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            article = ArticlePost(owner=user, title="Test Article")
            db_session.add(article)
            db_session.flush()

            card = PostCard(post=article)
            vm = card.get_post()

            assert isinstance(vm, ArticleVM)

    def test_get_post_with_press_release(self, db_session, app):
        """Test get_post returns PressReleaseVM for PressReleasePost."""
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            pr = PressReleasePost(owner=user, title="Test PR")
            db_session.add(pr)
            db_session.flush()

            card = PostCard(post=pr)
            vm = card.get_post()

            assert isinstance(vm, PressReleaseVM)

    def test_get_post_with_invalid_type_raises(self, app):
        """Test get_post raises ValueError for unsupported type."""
        with app.test_request_context():

            class FakePost:
                pass

            card = PostCard(post=FakePost())  # type: ignore[arg-type]

            with pytest.raises(ValueError, match="Unsupported post type"):
                card.get_post()


class TestArticleVM:
    """Test ArticleVM view model."""

    def test_summary_truncation(self, db_session, app):
        """Test summary is truncated to 200 chars."""
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            long_summary = "A" * 300
            article = ArticlePost(owner=user, title="Test", summary=long_summary)
            db_session.add(article)
            db_session.flush()

            vm = ArticleVM(article)
            assert len(vm.summary) == 200
            assert vm.summary.endswith("...")

    def test_summary_short_not_truncated(self, db_session, app):
        """Test short summary is not truncated."""
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            short_summary = "Short summary"
            article = ArticlePost(owner=user, title="Test", summary=short_summary)
            db_session.add(article)
            db_session.flush()

            vm = ArticleVM(article)
            assert vm.summary == short_summary

    def test_counts_from_post(self, db_session, app):
        """Test likes, replies, views come from post.

        Ticket #0193 — `views` is now the count of PAID
        CONSULTATION purchases on this post (eye-icon counter shows
        paying readers, not raw page views). Two PAID consultations
        → `vm.views == 2`. `Post.view_count` is no longer surfaced
        through the card view-model.
        """
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            buyer = User(email="buyer_card@example.com")
            db_session.add(buyer)
            db_session.flush()

            article = ArticlePost(owner=user, title="Test")
            article.like_count = 10
            article.comment_count = 5
            db_session.add(article)
            db_session.flush()

            for _ in range(2):
                db_session.add(
                    ArticlePurchase(
                        post_id=article.id,
                        owner_id=buyer.id,
                        product_type=PurchaseProduct.CONSULTATION,
                        status=PurchaseStatus.PAID,
                        amount_cents=100,
                        paid_at=datetime.now(UTC),
                    )
                )
            db_session.flush()

            vm = ArticleVM(article)
            assert vm.likes == 10
            assert vm.replies == 5
            assert vm.views == 2

    def test_image_url_default(self, db_session, app):
        """Test default image URL when no image."""
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            article = ArticlePost(owner=user, title="Test")
            db_session.add(article)
            db_session.flush()

            vm = ArticleVM(article)
            assert vm.image_url == "/static/img/gray-texture.png"

    def test_author_is_user_vm(self, db_session, app):
        """Test author is wrapped in UserVM."""
        with app.test_request_context():
            user = User(email="author@example.com", first_name="John", last_name="Doe")
            db_session.add(user)
            db_session.flush()

            article = ArticlePost(owner=user, title="Test")
            db_session.add(article)
            db_session.flush()

            vm = ArticleVM(article)
            assert isinstance(vm.author, UserVM)


class TestPressReleaseVM:
    """Test PressReleaseVM view model."""

    def test_summary_truncation(self, db_session, app):
        """Test summary is truncated to 200 chars."""
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            long_content = "B" * 300
            pr = PressReleasePost(owner=user, title="Test", content=long_content)
            db_session.add(pr)
            db_session.flush()

            vm = PressReleaseVM(pr)
            assert len(vm.summary) == 200
            assert vm.summary.endswith("...")

    def test_counts_from_post(self, db_session, app):
        """Test likes, replies, views come from post."""
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            pr = PressReleasePost(owner=user, title="Test")
            pr.like_count = 15
            pr.comment_count = 8
            pr.view_count = 200
            db_session.add(pr)
            db_session.flush()

            vm = PressReleaseVM(pr)
            assert vm.likes == 15
            assert vm.replies == 8
            assert vm.views == 200

    def test_image_url_default(self, db_session, app):
        """Test default image URL when no image."""
        with app.test_request_context():
            user = User(email="author@example.com")
            db_session.add(user)
            db_session.flush()

            pr = PressReleasePost(owner=user, title="Test")
            db_session.add(pr)
            db_session.flush()

            vm = PressReleaseVM(pr)
            assert vm.image_url == "/static/img/gray-texture.png"


class TestUserVM:
    """Test UserVM view model."""

    def test_get_organisation_with_no_org(self, db_session, app):
        """Test get_organisation returns None when user has no org."""
        with app.test_request_context():
            user = User(email="user@example.com")
            user.organisation_id = None
            db_session.add(user)
            db_session.flush()

            vm = UserVM(user)
            assert vm.get_organisation() is None


class TestPostCardSelfPublicationByline:
    """Bug #0093: a self-published communiqué (no client delegation)
    must show an author byline "Publié par <Nom>, <fonction> chez
    <organisation>." The card previously only rendered a byline for
    the *delegated* case (author org ≠ publisher), so a PR consultant
    publishing their own CP got no mention. The delegated phrasing
    must stay unchanged (no regression).
    """

    def _render(self, app, communique) -> str:
        with app.test_request_context():
            return render_template_string(
                '{{ component("post-card", c) }}', c=communique
            )

    @staticmethod
    def _pr_role(db_session) -> Role:
        role = Role(
            name=RoleEnum.PRESS_RELATIONS.name,
            description=RoleEnum.PRESS_RELATIONS.value,
        )
        db_session.add(role)
        db_session.flush()
        return role

    def test_self_published_cp_shows_author_fonction_org(self, db_session, app):
        org = Organisation(name="Fake-RoulezJeunesse")
        db_session.add(org)
        db_session.flush()
        user = User(
            email="cath@example.com",
            first_name="Catherine",
            last_name="Samorian",
        )
        user.profile = KYCProfile(profile_label="consultante en Relations Presse")
        user.organisation = org
        user.organisation_id = org.id
        user.roles.append(self._pr_role(db_session))
        db_session.add(user)
        db_session.flush()

        cp = Communique(owner=user, publisher=org)  # self-published
        cp.published_at = arrow.utcnow()
        db_session.add(cp)
        db_session.flush()

        html = self._render(app, cp)
        assert (
            "Publié par Catherine Samorian, consultante en Relations "
            "Presse chez Fake-RoulezJeunesse." in html
        )
        assert "en tant que contact presse de" not in html

    def test_delegated_cp_keeps_contact_presse_phrasing(self, db_session, app):
        agency = Organisation(name="Fake-Les Propulseurs PR")
        client_org = Organisation(name="Fake-Davi Logistique")
        db_session.add_all([agency, client_org])
        db_session.flush()
        user = User(email="igor@example.com", first_name="Igor", last_name="F")
        user.organisation = agency
        user.organisation_id = agency.id
        user.roles.append(self._pr_role(db_session))
        db_session.add(user)
        db_session.flush()

        cp = Communique(owner=user, publisher=client_org)  # delegated
        cp.published_at = arrow.utcnow()
        db_session.add(cp)
        db_session.flush()

        html = self._render(app, cp)
        assert (
            "Publié par Fake-Les Propulseurs PR en tant que contact "
            "presse de Fake-Davi Logistique." in html
        )
        assert "chez Fake-Les Propulseurs PR." not in html
