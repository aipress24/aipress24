# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0192 — /wip/ventes is the author-side counterpart of
/wip/achats. Lists PAID purchases on the user's own articles ; for
rédac chefs, also surfaces aggregated media-wide sales."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    BWStatus,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)
from app.settings.constants import PUBLISHER_REVENUE_SHARE_PERCENT

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"ventes_{uuid.uuid4().hex[:6]}@example.com"


@pytest.fixture
def article_by_test_user(
    db_session: Session, test_user: User, test_org: Organisation
) -> ArticlePost:
    """An article authored by `test_user`, published for `test_org`."""
    post = ArticlePost(
        title="Mon enquête",
        owner_id=test_user.id,
        publisher_id=test_org.id,
    )
    db_session.add(post)
    db_session.commit()
    return post


@pytest.fixture
def buyer(db_session: Session) -> User:
    """A separate buyer in their own org, used as the purchaser."""
    other_org = Organisation(name="Editor Inc.")
    db_session.add(other_org)
    db_session.commit()
    user = User(email=_email(), active=True, first_name="Buyer", last_name="Z")
    user.organisation = other_org
    user.organisation_id = other_org.id
    db_session.add(user)
    db_session.commit()
    return user


def _add_paid(
    db_session: Session,
    *,
    buyer: User,
    post: ArticlePost,
    amount_cents: int,
    product: PurchaseProduct = PurchaseProduct.CONSULTATION,
) -> ArticlePurchase:
    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=buyer.id,
        product_type=product,
        status=PurchaseStatus.PAID,
        amount_cents=amount_cents,
        paid_at=datetime.now(UTC),
    )
    db_session.add(purchase)
    db_session.commit()
    return purchase


class TestVentesViewBase:
    def test_page_loads_for_authenticated_journalist(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        response = logged_in_client.get("/wip/ventes")
        assert response.status_code == 200
        body = response.data.decode()
        assert "vente" in body.lower()

    def test_empty_state_when_no_sales(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        response = logged_in_client.get("/wip/ventes")
        body = response.data.decode()
        assert "pas encore de vente" in body

    def test_lists_paid_sales_on_users_own_articles(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        article_by_test_user: ArticlePost,
        buyer: User,
    ):
        _add_paid(
            db_session,
            buyer=buyer,
            post=article_by_test_user,
            amount_cents=2500,
            product=PurchaseProduct.CONSULTATION,
        )
        _add_paid(
            db_session,
            buyer=buyer,
            post=article_by_test_user,
            amount_cents=4500,
            product=PurchaseProduct.CESSION,
        )

        response = logged_in_client.get("/wip/ventes")
        body = response.data.decode()

        assert "Mon enquête" in body
        assert "25.00" in body
        assert "45.00" in body
        # Cumul own = 25 + 45 = 70.00 €
        assert "70.00" in body

    def test_excludes_pending_and_refunded(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        article_by_test_user: ArticlePost,
        buyer: User,
    ):
        _add_paid(
            db_session,
            buyer=buyer,
            post=article_by_test_user,
            amount_cents=1000,
        )
        # noise that must not appear in the total
        for status in (PurchaseStatus.PENDING, PurchaseStatus.REFUNDED):
            db_session.add(
                ArticlePurchase(
                    post_id=article_by_test_user.id,
                    owner_id=buyer.id,
                    product_type=PurchaseProduct.CONSULTATION,
                    status=status,
                    amount_cents=8888,
                )
            )
        db_session.commit()

        response = logged_in_client.get("/wip/ventes")
        body = response.data.decode()
        assert "10.00" in body
        assert "88.88" not in body

    def test_shows_publisher_share(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        article_by_test_user: ArticlePost,
        buyer: User,
    ):
        """#0364 — the sale amount is shared with the platform, so the
        page shows the publisher's part next to it, per sale and in the
        cumul."""
        _add_paid(db_session, buyer=buyer, post=article_by_test_user, amount_cents=3000)
        _add_paid(db_session, buyer=buyer, post=article_by_test_user, amount_cents=50)

        body = logged_in_client.get("/wip/ventes").data.decode()

        assert "Part éditeur" in body
        share = PUBLISHER_REVENUE_SHARE_PERCENT / 100
        assert f"{30.00 * share:.2f} €" in body
        assert f"{0.50 * share:.2f} €" in body
        assert f"dont part éditeur : {30.50 * share:.2f} € HT" in body

    def test_gift_sale_has_a_readable_label(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        article_by_test_user: ArticlePost,
        buyer: User,
    ):
        """#0364 — a gifted consultation showed its raw product code."""
        _add_paid(
            db_session,
            buyer=buyer,
            post=article_by_test_user,
            amount_cents=100,
            product=PurchaseProduct.CONSULTATION_GIFT,
        )

        body = logged_in_client.get("/wip/ventes").data.decode()

        assert "Consultation offerte" in body
        assert "consultation_gift" not in body

    def test_article_link_opens_the_article(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        article_by_test_user: ArticlePost,
        buyer: User,
    ):
        """#0365 — the title used to link to `/wire/item/<id>`, a route
        that does not exist, so every click ended on a 404."""
        _add_paid(db_session, buyer=buyer, post=article_by_test_user, amount_cents=100)

        body = logged_in_client.get("/wip/ventes").data.decode()
        match = re.search(r'href="([^"]+)"[^>]*>Mon enquête<', body)
        assert match is not None

        response = logged_in_client.get(match.group(1))
        assert response.status_code == 200
        assert "Mon enquête" in response.data.decode()


class TestVentesViewRedacChef:
    """Tickets #0193–#0196 : « Les ventes de tous les auteurs
    convergent dans son espace WORK/Ventes du rédac chef »."""

    @pytest.fixture
    def make_redac_chef(self, db_session: Session, test_user: User):
        """Promote `test_user` to rédac chef of their org by assigning
        a PM_DIR profile."""
        if test_user.profile is None:
            test_user.profile = KYCProfile(profile_code="PM_DIR")
        else:
            test_user.profile.profile_code = "PM_DIR"
        db_session.commit()
        return test_user

    def test_media_section_hidden_for_non_redac_chef(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        # `test_user`'s default profile has no PM_DIR code.
        response = logged_in_client.get("/wip/ventes")
        body = response.data.decode()
        assert "rédacteur en chef" not in body

    def test_media_section_visible_for_redac_chef(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        make_redac_chef,
    ):
        response = logged_in_client.get("/wip/ventes")
        body = response.data.decode()
        assert "rédacteur en chef" in body
        assert "Cumul des ventes du média" in body

    def test_media_section_visible_for_business_wall_manager(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ):
        """The rédac chef of the sujets: managing the media's Business Wall
        qualifies, without the PM_DIR title."""
        bw = BusinessWall(
            bw_type="media",
            status=BWStatus.ACTIVE.value,
            is_free=True,
            owner_id=test_user.id,
            payer_id=test_user.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()
        db_session.add(
            RoleAssignment(
                business_wall_id=bw.id,
                user_id=test_user.id,
                role_type=BWRoleType.BW_OWNER.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )
        db_session.commit()

        body = logged_in_client.get("/wip/ventes").data.decode()

        assert "Cumul des ventes du média" in body

    def test_media_section_aggregates_other_authors(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
        buyer: User,
        make_redac_chef,
    ):
        """Annick (rédac chef) sees Nicolas's sales on her media's
        articles, even though Nicolas authored them."""
        nicolas = User(
            email=_email(),
            active=True,
            first_name="Nicolas",
            last_name="Mouriou",
        )
        nicolas.organisation = test_org
        nicolas.organisation_id = test_org.id
        db_session.add(nicolas)
        db_session.commit()
        # Nicolas authors a post PUBLISHED under test_org (the media).
        nicolas_post = ArticlePost(
            title="Article de Nicolas",
            owner_id=nicolas.id,
            publisher_id=test_org.id,
        )
        db_session.add(nicolas_post)
        db_session.commit()
        _add_paid(
            db_session,
            buyer=buyer,
            post=nicolas_post,
            amount_cents=3000,
        )

        response = logged_in_client.get("/wip/ventes")
        body = response.data.decode()

        # Annick's *own* cumul is 0 (she didn't author Nicolas's post).
        # But the media section must show 30.00 €.
        assert "Article de Nicolas" in body
        # Both the row amount and the media cumul are 30.00.
        assert body.count("30.00") >= 2
