# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0194 — CdAO data layer : `CONSULTATION_GIFT` purchases
grant paywall access to N beneficiaries, count toward the Vue counter,
and refuse to gift someone who already has access."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.auth import User
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    ArticlePurchaseGift,
    PurchaseProduct,
    PurchaseStatus,
)
from app.modules.wire.services.article_access import user_can_read_full
from app.modules.wire.services.purchase_aggregates import (
    get_paid_consultations_count,
    is_consultation_giftable_to,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _user(db_session: Session, email: str) -> User:
    user = User(email=email, active=True, first_name="X", last_name="Y")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def author(db_session: Session) -> User:
    return _user(db_session, "gift_author@example.com")


@pytest.fixture
def buyer(db_session: Session) -> User:
    return _user(db_session, "gift_buyer@example.com")


@pytest.fixture
def alice(db_session: Session) -> User:
    return _user(db_session, "gift_alice@example.com")


@pytest.fixture
def bob(db_session: Session) -> User:
    return _user(db_session, "gift_bob@example.com")


@pytest.fixture
def post(db_session: Session, author: User) -> ArticlePost:
    p = ArticlePost(title="Article cadeau", owner_id=author.id)
    db_session.add(p)
    db_session.flush()
    return p


def _gift_purchase(
    db_session: Session,
    *,
    buyer: User,
    post: ArticlePost,
    beneficiaries: list[User],
    amount_cents: int,
    status: PurchaseStatus = PurchaseStatus.PAID,
) -> ArticlePurchase:
    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=buyer.id,
        product_type=PurchaseProduct.CONSULTATION_GIFT,
        status=status,
        amount_cents=amount_cents,
        paid_at=datetime.now(UTC) if status == PurchaseStatus.PAID else None,
    )
    db_session.add(purchase)
    db_session.flush()
    for b in beneficiaries:
        db_session.add(
            ArticlePurchaseGift(
                purchase_id=purchase.id,
                beneficiary_user_id=b.id,
            )
        )
    db_session.flush()
    return purchase


class TestPaywallGrantsAccessToBeneficiaries:
    def test_beneficiary_can_read_full_after_paid_gift(
        self,
        db_session: Session,
        buyer: User,
        post: ArticlePost,
        alice: User,
        bob: User,
    ):
        _gift_purchase(
            db_session,
            buyer=buyer,
            post=post,
            beneficiaries=[alice, bob],
            amount_cents=200,
        )
        assert user_can_read_full(alice, post) is True
        assert user_can_read_full(bob, post) is True

    def test_non_beneficiary_still_blocked(
        self,
        db_session: Session,
        buyer: User,
        post: ArticlePost,
        alice: User,
        bob: User,
    ):
        """Alice is gifted ; Bob isn't named on the gift → Bob still
        sees the paywall."""
        _gift_purchase(
            db_session,
            buyer=buyer,
            post=post,
            beneficiaries=[alice],
            amount_cents=100,
        )
        assert user_can_read_full(alice, post) is True
        assert user_can_read_full(bob, post) is False

    def test_pending_gift_does_not_grant_access(
        self,
        db_session: Session,
        buyer: User,
        post: ArticlePost,
        alice: User,
    ):
        """A gift that hasn't been PAID yet must not lift the paywall."""
        _gift_purchase(
            db_session,
            buyer=buyer,
            post=post,
            beneficiaries=[alice],
            amount_cents=100,
            status=PurchaseStatus.PENDING,
        )
        assert user_can_read_full(alice, post) is False

    def test_buyer_does_not_get_access_unless_named_as_beneficiary(
        self,
        db_session: Session,
        buyer: User,
        post: ArticlePost,
        alice: User,
    ):
        """The buyer pays for the gift but doesn't automatically read
        the article — they have to gift themselves explicitly (or buy
        a regular CONSULTATION)."""
        _gift_purchase(
            db_session,
            buyer=buyer,
            post=post,
            beneficiaries=[alice],
            amount_cents=100,
        )
        assert user_can_read_full(buyer, post) is False


class TestVueCounterIncludesGifts:
    def test_gift_beneficiaries_count_toward_vue_counter(
        self,
        db_session: Session,
        buyer: User,
        post: ArticlePost,
        alice: User,
        bob: User,
    ):
        # 3 PAID gift beneficiaries (alice, bob, and a re-gift via a
        # second gift purchase) → counter shows 3.
        _gift_purchase(
            db_session,
            buyer=buyer,
            post=post,
            beneficiaries=[alice, bob],
            amount_cents=200,
        )
        carol = _user(db_session, "gift_carol@example.com")
        _gift_purchase(
            db_session,
            buyer=buyer,
            post=post,
            beneficiaries=[carol],
            amount_cents=100,
        )

        assert get_paid_consultations_count(post.id) == 3

    def test_direct_and_gift_purchases_both_count(
        self,
        db_session: Session,
        buyer: User,
        post: ArticlePost,
        alice: User,
    ):
        """One direct CONSULTATION + one gift to alice → counter = 2."""
        db_session.add(
            ArticlePurchase(
                post_id=post.id,
                owner_id=buyer.id,
                product_type=PurchaseProduct.CONSULTATION,
                status=PurchaseStatus.PAID,
                amount_cents=100,
                paid_at=datetime.now(UTC),
            )
        )
        _gift_purchase(
            db_session,
            buyer=buyer,
            post=post,
            beneficiaries=[alice],
            amount_cents=100,
        )
        assert get_paid_consultations_count(post.id) == 2

    def test_pending_gifts_do_not_count(
        self,
        db_session: Session,
        buyer: User,
        post: ArticlePost,
        alice: User,
    ):
        _gift_purchase(
            db_session,
            buyer=buyer,
            post=post,
            beneficiaries=[alice],
            amount_cents=100,
            status=PurchaseStatus.PENDING,
        )
        assert get_paid_consultations_count(post.id) == 0


class TestIsConsultationGiftableTo:
    def test_giftable_to_a_fresh_recipient(
        self,
        db_session: Session,
        post: ArticlePost,
        alice: User,
    ):
        assert is_consultation_giftable_to(alice.id, post.id) is True

    def test_not_giftable_when_already_owns_a_consultation(
        self,
        db_session: Session,
        post: ArticlePost,
        alice: User,
    ):
        """Alice already bought a PAID CONSULTATION → don't waste the
        buyer's money."""
        db_session.add(
            ArticlePurchase(
                post_id=post.id,
                owner_id=alice.id,
                product_type=PurchaseProduct.CONSULTATION,
                status=PurchaseStatus.PAID,
                amount_cents=100,
                paid_at=datetime.now(UTC),
            )
        )
        db_session.flush()
        assert is_consultation_giftable_to(alice.id, post.id) is False

    def test_not_giftable_when_already_beneficiary_of_a_gift(
        self,
        db_session: Session,
        buyer: User,
        post: ArticlePost,
        alice: User,
    ):
        """Alice was gifted on this post → a second gift would be
        redundant. Refuse."""
        _gift_purchase(
            db_session,
            buyer=buyer,
            post=post,
            beneficiaries=[alice],
            amount_cents=100,
        )
        assert is_consultation_giftable_to(alice.id, post.id) is False

    def test_giftable_after_only_a_pending_consultation(
        self,
        db_session: Session,
        post: ArticlePost,
        alice: User,
    ):
        """A PENDING (unpaid) consultation doesn't grant access yet,
        so a gift is still useful."""
        db_session.add(
            ArticlePurchase(
                post_id=post.id,
                owner_id=alice.id,
                product_type=PurchaseProduct.CONSULTATION,
                status=PurchaseStatus.PENDING,
                amount_cents=100,
            )
        )
        db_session.flush()
        assert is_consultation_giftable_to(alice.id, post.id) is True

    def test_returns_true_for_unknown_input(self):
        """Defensive : caller should validate upstream ; helper
        returns True for unknown ids so it never falsely blocks a
        legitimate gift attempt."""
        assert is_consultation_giftable_to(None, 1) is True
        assert is_consultation_giftable_to(1, None) is True
        assert is_consultation_giftable_to(0, 0) is True


class TestGiftUniqueness:
    def test_same_purchase_cannot_gift_same_beneficiary_twice(
        self,
        db_session: Session,
        buyer: User,
        post: ArticlePost,
        alice: User,
    ):
        """The (purchase_id, beneficiary_user_id) unique constraint
        prevents inserting the same beneficiary twice on a single
        purchase. Two distinct purchases can each gift Alice, but a
        single purchase can't list her twice."""
        purchase = ArticlePurchase(
            post_id=post.id,
            owner_id=buyer.id,
            product_type=PurchaseProduct.CONSULTATION_GIFT,
            status=PurchaseStatus.PAID,
            amount_cents=100,
            paid_at=datetime.now(UTC),
        )
        db_session.add(purchase)
        db_session.flush()
        db_session.add(
            ArticlePurchaseGift(
                purchase_id=purchase.id,
                beneficiary_user_id=alice.id,
            )
        )
        db_session.flush()
        db_session.add(
            ArticlePurchaseGift(
                purchase_id=purchase.id,
                beneficiary_user_id=alice.id,
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()
