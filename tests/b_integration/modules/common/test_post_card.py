# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for common/components/post_card.py."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import arrow
import pytest
from app.enums import BWType, RoleEnum
from app.lib.file_object_utils import create_file_object
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.common.components.post_card import (
    ArticleVM,
    CommuniqueVM,
    PostCard,
    PressReleaseVM,
    UserVM,
)
from app.modules.wip.models.comroom import ComImage, Communique
from app.modules.wip.models.newsroom import Article, Image
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PressReleasePost,
    PurchaseProduct,
    PurchaseStatus,
)
from flask import render_template_string


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


class TestCardImageUrl:
    """Bug 0268 : la vignette de la carte pointait sur
    `/wip/articles/<id>/images/<image_id>`, une route de l'espace de
    travail qui lève 404 dès que `Post.image_id` — figé au moment de la
    publication — ne désigne plus une image existante. C'est ce qui
    arrive quand l'auteur supprime puis republie son article : le
    carrousel de la page détaillée restait correct (il relit les images
    de l'article) mais la carte affichait une image cassée.

    La carte doit désormais servir l'URL du média elle-même, comme le
    carrousel, et retomber sur le placeholder si l'image a disparu.
    """

    def _article_image(self, db_session):
        """An `Article` carrying one stored image, and that image."""
        owner = User(email=f"img-owner-{uuid.uuid4().hex[:6]}@example.com")
        media = Organisation(name=f"Media {uuid.uuid4().hex[:6]}")
        db_session.add_all([owner, media])
        db_session.flush()

        article = Article(
            owner=owner,
            media=media,
            # `commanditaire_id` points at a User, `publisher_id` at an
            # Organisation. PostgreSQL enforces both FKs; SQLite does not.
            commanditaire_id=owner.id,
            publisher_id=media.id,
            date_parution_prevue=arrow.now().datetime,
        )
        db_session.add(article)
        db_session.flush()

        image = Image(
            owner=owner,
            article_id=article.id,
            content=create_file_object(
                content=b"fake-jpeg-bytes",
                original_filename="photo.jpg",
                content_type="image/jpeg",
            ),
        )
        db_session.add(image)
        db_session.flush()
        return owner, article, image

    def test_card_serves_the_media_url_not_a_wip_route(self, db_session, app):
        with app.test_request_context():
            owner, article, image = self._article_image(db_session)

            post = ArticlePost(owner=owner, title="Automobile")
            post.newsroom_id = article.id
            post.image_id = image.id
            db_session.add(post)
            db_session.flush()

            card_url = ArticleVM(post).image_url
            assert card_url == image.url
            # Not the placeholder, and not the /wip route that used to 404.
            assert card_url.startswith("/media/")

    def test_rendered_card_points_its_img_at_the_media_url(self, db_session, app):
        """The wiring, not just the view-model : the rendered `<img>` is
        what 404'd in Erick's browser."""
        with app.test_request_context():
            owner, article, image = self._article_image(db_session)

            post = ArticlePost(owner=owner, title="Automobile")
            post.newsroom_id = article.id
            post.image_id = image.id
            post.published_at = arrow.now()
            db_session.add(post)
            db_session.flush()

            html = render_template_string('{{ component("post-card", c) }}', c=post)

            assert f'src="{image.url}"' in html
            assert "/wip/articles/" not in html

    def test_dangling_image_id_falls_back_to_the_placeholder(self, db_session, app):
        """The regression itself : a `Post` whose `image_id` no longer
        resolves must degrade to the placeholder rather than emit a URL
        that 404s in the browser."""
        with app.test_request_context():
            owner, article, image = self._article_image(db_session)

            post = ArticlePost(owner=owner, title="Republié")
            post.newsroom_id = article.id
            post.image_id = image.id
            db_session.add(post)
            db_session.flush()

            # The author deleted the image (or the whole article — the
            # `nrm_image.article_id` FK cascades) and re-published.
            db_session.delete(image)
            db_session.flush()

            assert ArticleVM(post).image_url == "/static/img/gray-texture.png"

    def test_press_release_card_also_serves_the_media_url(self, db_session, app):
        with app.test_request_context():
            owner = User(email=f"cp-owner-{uuid.uuid4().hex[:6]}@example.com")
            db_session.add(owner)
            db_session.flush()

            communique = Communique(owner=owner, titre="CP")
            db_session.add(communique)
            db_session.flush()

            com_image = ComImage(
                owner=owner,
                communique_id=communique.id,
                content=create_file_object(
                    content=b"fake-png-bytes",
                    original_filename="visuel.png",
                    content_type="image/png",
                ),
            )
            db_session.add(com_image)
            db_session.flush()

            pr = PressReleasePost(owner=owner, title="CP")
            pr.newsroom_id = communique.id
            pr.image_id = com_image.id
            db_session.add(pr)
            db_session.flush()

            card_url = PressReleaseVM(pr).image_url
            assert card_url == com_image.url
            assert card_url.startswith("/media/")


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
        # Ticket #0325 : « / » et non « chez ». Erick demande
        # « Prénom, Nom, Fonction / Nom de l'organisation », précisément
        # pour éviter d'avoir à choisir entre « chez », « à » et « au ».
        assert (
            "Publié par Catherine Samorian, consultante en Relations "
            "Presse / Fake-RoulezJeunesse." not in html
        )
        assert " chez " not in html
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


class TestPostCardArticleByline:
    """Bug 0241: a News-Agency (or media) ARTICLE must never use the PR
    « en tant que contact presse de » phrasing — that formulation is
    reserved for communiqués (a PR agency publishing a CP for a client).
    An article always surfaces its author, fonction and organisation,
    even when the publisher org differs from the author's own org.
    """

    def _render(self, app, post) -> str:
        with app.test_request_context():
            return render_template_string('{{ component("post-card", c) }}', c=post)

    def test_delegated_article_uses_author_byline_not_contact_presse(
        self, db_session, app
    ):
        author_org = Organisation(name="Agence TCA")
        publisher_org = Organisation(name="Fake-Les Echolos")
        media_org = Organisation(name="Le Média Cible")
        db_session.add_all([author_org, publisher_org, media_org])
        db_session.flush()

        user = User(email="eliane@example.com", first_name="Eliane", last_name="Kan")
        user.profile = KYCProfile(
            profile_label="Dirigeant.e d'organes de presse ou média reconnus"
        )
        user.organisation = author_org
        user.organisation_id = author_org.id
        db_session.add(user)
        db_session.flush()

        # Delegated: the article's publisher org differs from the author's org.
        article = ArticlePost(owner=user, title="Automobile")
        article.publisher_id = publisher_org.id
        article.media_id = media_org.id
        article.published_at = arrow.utcnow()
        db_session.add(article)
        db_session.flush()

        html = self._render(app, article)
        assert "en tant que contact presse de" not in html
        assert "Publié par Eliane Kan" not in html
        # Ticket #0325 : le séparateur remplace « chez ».
        assert "/ Agence TCA" in html
        # Bug 0241: the footer uses the "Source :" / "Pour :" labels.
        assert "Source :" in html
        assert "Pour :" in html


class TestPostCardNewsAgencyMacaron:
    """Test display the press agency logo for articles from NEWS_AGENCY."""

    MACARON = "MacaronSourceAgenceDePresse_32px.jpg"

    def _render(self, app, post) -> str:
        with app.test_request_context():
            return render_template_string('{{ component("post-card", c) }}', c=post)

    def test_article_published_by_news_agency_shows_macaron(self, db_session, app):
        agency_org = Organisation(name="AFP", bw_active=BWType.NEWS_AGENCY.value)
        db_session.add(agency_org)
        db_session.flush()

        user = User(
            email="afp_journalist@example.com",
            first_name="Jean",
            last_name="Dupont",
        )
        user.organisation = agency_org
        user.organisation_id = agency_org.id
        db_session.add(user)
        db_session.flush()

        article = ArticlePost(owner=user, title="news", publisher_id=agency_org.id)
        article.published_at = arrow.utcnow()
        db_session.add(article)
        db_session.flush()

        vm = ArticleVM(article)
        assert vm.is_news_agency is True

        html = self._render(app, article)
        assert self.MACARON in html
        assert 'title="Source agence de presse"' in html

    def test_article_by_author_in_news_agency_shows_macaron(self, db_session, app):
        agency_org = Organisation(name="Reuters", bw_active=BWType.NEWS_AGENCY.value)
        db_session.add(agency_org)
        db_session.flush()

        user = User(
            email="reuters_journalist@example.com",
            first_name="Alice",
            last_name="Martin",
        )
        user.organisation = agency_org
        user.organisation_id = agency_org.id
        db_session.add(user)
        db_session.flush()

        article = ArticlePost(owner=user, title="Flash info")
        article.published_at = arrow.utcnow()
        db_session.add(article)
        db_session.flush()

        vm = ArticleVM(article)
        assert vm.is_news_agency is True

        html = self._render(app, article)
        assert self.MACARON in html

    def test_regular_media_article_does_not_show_macaron(self, db_session, app):
        media_org = Organisation(name="Journal", bw_active=BWType.MEDIA.value)
        db_session.add(media_org)
        db_session.flush()

        user = User(
            email="journalist@example.com",
            first_name="Paul",
            last_name="Durand",
        )
        user.organisation = media_org
        user.organisation_id = media_org.id
        db_session.add(user)
        db_session.flush()

        article = ArticlePost(
            owner=user, title="Article classique", publisher_id=media_org.id
        )
        article.published_at = arrow.utcnow()
        db_session.add(article)
        db_session.flush()

        vm = ArticleVM(article)
        assert vm.is_news_agency is False

        html = self._render(app, article)
        assert self.MACARON not in html

    def test_communique_does_not_show_macaron(self, db_session, app):
        agency_org = Organisation(name="Agence PR", bw_active=BWType.NEWS_AGENCY.value)
        db_session.add(agency_org)
        db_session.flush()

        user = User(email="pr@example.com", first_name="Sophie", last_name="L")
        user.organisation = agency_org
        user.organisation_id = agency_org.id
        db_session.add(user)
        db_session.flush()

        cp = Communique(owner=user, publisher=agency_org, titre="Communiqué spécial")
        cp.published_at = arrow.utcnow()
        db_session.add(cp)
        db_session.flush()

        vm = CommuniqueVM(cp)
        assert vm.is_news_agency is False

        html = self._render(app, cp)
        assert self.MACARON not in html
