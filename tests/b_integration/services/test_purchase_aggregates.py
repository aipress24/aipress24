# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0193 – #0196 — every buy pop-up must show « le cumul de vos
achats éditoriaux » and « celui de votre organisation ». Tested at the
helper level so the same numbers will appear in the pop-ups, in
WORK/Achats, and in the future admin recap dashboards."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models.business_wall import BusinessWall
from app.modules.bw.bw_activation.models.role import (
    InvitationStatus,
    RoleAssignment,
)
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    ArticlePurchaseGift,
    PurchaseProduct,
    PurchaseStatus,
)
from app.modules.wire.services.purchase_aggregates import (
    count_org_press_book,
    count_user_press_book,
    get_media_sales_total,
    get_org_purchase_total,
    get_paid_consultations_count,
    get_paid_consultations_counts,
    get_post_sales_amount,
    get_user_purchase_total,
    get_user_sales_total,
    list_org_press_book,
    list_paid_purchases,
    list_purchases_per_org,
    list_sales_per_media,
    list_user_press_book,
    list_user_received_gifts,
)
from app.settings.constants import ARTICLE_CONSULTATION_DURATION

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _make_post(db_session: Session, owner: User) -> ArticlePost:
    post = ArticlePost(title="A", owner_id=owner.id)
    db_session.add(post)
    db_session.flush()
    return post


def _make_purchase(
    db_session: Session,
    *,
    user: User,
    post: ArticlePost,
    amount_cents: int,
    status: PurchaseStatus,
    product: PurchaseProduct = PurchaseProduct.CONSULTATION,
) -> ArticlePurchase:
    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=user.id,
        product_type=product,
        status=status,
        amount_cents=amount_cents,
    )
    db_session.add(purchase)
    db_session.flush()
    return purchase


@pytest.fixture
def org(db_session: Session) -> Organisation:
    org = Organisation(name="ACME Inc.")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def alice(db_session: Session, org: Organisation) -> User:
    u = User(email="alice@acme.example", first_name="Alice", last_name="A", active=True)
    u.organisation = org
    u.organisation_id = org.id
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def bob(db_session: Session, org: Organisation) -> User:
    u = User(email="bob@acme.example", first_name="Bob", last_name="B", active=True)
    u.organisation = org
    u.organisation_id = org.id
    db_session.add(u)
    db_session.flush()
    return u


@pytest.fixture
def carol(db_session: Session) -> User:
    """Carol is at a DIFFERENT organisation — used to prove the org
    aggregate doesn't bleed cross-org."""
    other_org = Organisation(name="Other Co.")
    other_org.id = 99_999  # avoid collision with the `org` fixture
    db_session.add(other_org)
    db_session.flush()
    u = User(
        email="carol@other.example", first_name="Carol", last_name="C", active=True
    )
    u.organisation = other_org
    u.organisation_id = other_org.id
    db_session.add(u)
    db_session.flush()
    return u


class TestGetUserPurchaseTotal:
    def test_sums_paid_purchases_only(self, db_session: Session, alice: User):
        post = _make_post(db_session, alice)
        _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=500,
            status=PurchaseStatus.PAID,
        )
        _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=750,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )
        # Should NOT count : pending + refunded.
        _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=999,
            status=PurchaseStatus.PENDING,
        )
        _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=999,
            status=PurchaseStatus.REFUNDED,
        )

        assert get_user_purchase_total(alice.id) == 1250

    def test_returns_zero_when_no_purchases(self, db_session: Session, alice: User):
        assert get_user_purchase_total(alice.id) == 0

    @pytest.mark.parametrize("user_id", [None, 0])
    def test_returns_zero_for_anonymous(self, user_id: int | None):
        assert get_user_purchase_total(user_id) == 0


class TestGetOrgPurchaseTotal:
    def test_sums_paid_purchases_across_org_members(
        self,
        db_session: Session,
        org: Organisation,
        alice: User,
        bob: User,
    ):
        post = _make_post(db_session, alice)
        _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=500,
            status=PurchaseStatus.PAID,
        )
        _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=300,
            status=PurchaseStatus.PAID,
        )

        assert get_org_purchase_total(org.id) == 800

    def test_does_not_count_purchases_from_other_orgs(
        self,
        db_session: Session,
        org: Organisation,
        alice: User,
        carol: User,
    ):
        """Alice (ACME) and Carol (Other Co.) each buy. The ACME
        aggregate must contain only Alice's purchase."""
        post = _make_post(db_session, alice)
        _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=500,
            status=PurchaseStatus.PAID,
        )
        _make_purchase(
            db_session,
            user=carol,
            post=post,
            amount_cents=10_000,
            status=PurchaseStatus.PAID,
        )

        assert get_org_purchase_total(org.id) == 500

    def test_returns_zero_for_missing_org(self):
        assert get_org_purchase_total(None) == 0
        assert get_org_purchase_total(0) == 0


class TestGetUserSalesTotal:
    def test_sums_paid_purchases_made_on_articles_owned_by_user(
        self, db_session: Session, alice: User, bob: User
    ):
        """Alice authored a post ; Bob bought it. Alice's sales
        aggregate must include Bob's PAID purchase."""
        alice_post = _make_post(db_session, alice)
        _make_purchase(
            db_session,
            user=bob,
            post=alice_post,
            amount_cents=1500,
            status=PurchaseStatus.PAID,
        )
        _make_purchase(
            db_session,
            user=bob,
            post=alice_post,
            amount_cents=600,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )
        # A PENDING purchase doesn't count toward sales either.
        _make_purchase(
            db_session,
            user=bob,
            post=alice_post,
            amount_cents=999,
            status=PurchaseStatus.PENDING,
        )

        assert get_user_sales_total(alice.id) == 2100

    def test_does_not_count_purchases_on_other_users_articles(
        self, db_session: Session, alice: User, bob: User
    ):
        """Bob authored a post Alice bought. That sale belongs to
        Bob, not Alice."""
        bob_post = _make_post(db_session, bob)
        _make_purchase(
            db_session,
            user=alice,
            post=bob_post,
            amount_cents=999,
            status=PurchaseStatus.PAID,
        )

        assert get_user_sales_total(alice.id) == 0

    @pytest.mark.parametrize("user_id", [None, 0])
    def test_returns_zero_for_missing_user(self, user_id: int | None):
        assert get_user_sales_total(user_id) == 0


class TestGetMediaSalesTotal:
    def test_sums_paid_purchases_on_posts_published_by_media(
        self,
        db_session: Session,
        org: Organisation,
        alice: User,
        bob: User,
        carol: User,
    ):
        """Alice publishes for ACME (her org). Carol buys her article.
        ACME's media sales total includes Carol's purchase."""
        alice_post = _make_post(db_session, alice)
        alice_post.publisher_id = org.id
        db_session.flush()
        _make_purchase(
            db_session,
            user=carol,
            post=alice_post,
            amount_cents=2000,
            status=PurchaseStatus.PAID,
        )

        assert get_media_sales_total(org.id) == 2000

    def test_aggregates_across_multiple_authors_of_the_same_media(
        self,
        db_session: Session,
        org: Organisation,
        alice: User,
        bob: User,
        carol: User,
    ):
        """Alice AND Bob both publish under ACME. Carol buys from
        each. ACME's total is the sum."""
        alice_post = _make_post(db_session, alice)
        alice_post.publisher_id = org.id
        bob_post = _make_post(db_session, bob)
        bob_post.publisher_id = org.id
        db_session.flush()
        _make_purchase(
            db_session,
            user=carol,
            post=alice_post,
            amount_cents=1000,
            status=PurchaseStatus.PAID,
        )
        _make_purchase(
            db_session,
            user=carol,
            post=bob_post,
            amount_cents=3000,
            status=PurchaseStatus.PAID,
        )

        assert get_media_sales_total(org.id) == 4000

    def test_returns_zero_for_missing_media(self):
        assert get_media_sales_total(None) == 0
        assert get_media_sales_total(0) == 0


class TestGetPaidConsultationsCount:
    def test_counts_paid_consultations_only(
        self, db_session: Session, alice: User, bob: User
    ):
        """Three CONSULTATION purchases on the same post — only PAID
        ones count toward the Vue counter."""
        post = _make_post(db_session, alice)
        _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=100,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION,
        )
        _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=100,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION,
        )
        _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=100,
            status=PurchaseStatus.PENDING,
            product=PurchaseProduct.CONSULTATION,
        )
        # Justificatif on the same post must NOT count.
        _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=200,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )

        assert get_paid_consultations_count(post.id) == 2

    def test_returns_zero_for_missing_or_zero_id(self):
        assert get_paid_consultations_count(None) == 0
        assert get_paid_consultations_count(0) == 0


class TestGetPaidConsultationsCounts:
    def test_batches_counts_per_post(self, db_session: Session, alice: User, bob: User):
        p1 = _make_post(db_session, alice)
        p2 = _make_post(db_session, alice)
        _make_purchase(
            db_session,
            user=bob,
            post=p1,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION,
        )
        _make_purchase(
            db_session,
            user=bob,
            post=p1,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION,
        )
        _make_purchase(
            db_session,
            user=bob,
            post=p2,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION,
        )

        counts = get_paid_consultations_counts([p1.id, p2.id])
        assert counts == {p1.id: 2, p2.id: 1}

    def test_returns_empty_for_empty_input(self):
        assert get_paid_consultations_counts([]) == {}

    def test_missing_ids_absent_from_dict(self, db_session: Session, alice: User):
        """A post with zero PAID consultations doesn't appear in the
        dict at all — the caller defaults to 0."""
        post = _make_post(db_session, alice)
        counts = get_paid_consultations_counts([post.id, 999_999])
        assert post.id not in counts or counts[post.id] == 0
        assert 999_999 not in counts

    def test_batched_agrees_with_singular_on_mixed_gifts(
        self, db_session: Session, alice: User, bob: User
    ):
        """The batched helper must produce the same number as the
        singular when a post has BOTH direct consultations AND
        CONSULTATION_GIFT beneficiaries. Otherwise any caller migrating
        to the batched helper silently regresses the eye-icon counter."""
        post = _make_post(db_session, alice)
        # 2 direct PAID consultations from another buyer.
        for _ in range(2):
            _make_purchase(
                db_session,
                user=bob,
                post=post,
                amount_cents=100,
                status=PurchaseStatus.PAID,
                product=PurchaseProduct.CONSULTATION,
            )
        # 1 PAID gift with 5 beneficiaries — real users so the FK
        # constraint on Postgres holds (SQLite leaves FKs off by
        # default and tolerated fake ids).
        beneficiaries = [
            User(email=f"gift_b{i}@example.com", active=True) for i in range(5)
        ]
        for b in beneficiaries:
            db_session.add(b)
        db_session.flush()

        gift_purchase = _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=500,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION_GIFT,
        )
        for b in beneficiaries:
            db_session.add(
                ArticlePurchaseGift(
                    purchase_id=gift_purchase.id,
                    beneficiary_user_id=b.id,
                )
            )
        db_session.flush()

        singular = get_paid_consultations_count(post.id)
        batched = get_paid_consultations_counts([post.id])
        assert singular == 2 + 5
        assert batched.get(post.id) == singular


class TestGetPostSalesAmount:
    def test_sums_paid_purchases_across_product_types(
        self, db_session: Session, alice: User, bob: User
    ):
        post = _make_post(db_session, alice)
        _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=2500,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION,
        )
        _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=5000,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CESSION,
        )
        # PENDING / REFUNDED ignored.
        _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=8888,
            status=PurchaseStatus.PENDING,
            product=PurchaseProduct.CONSULTATION,
        )

        assert get_post_sales_amount(post.id) == 7500

    def test_returns_zero_for_missing_id(self):
        assert get_post_sales_amount(None) == 0
        assert get_post_sales_amount(0) == 0


class TestListUserPressBook:
    def test_lists_articles_with_paid_justificatif_owned_by_user(
        self, db_session: Session, alice: User, bob: User
    ):
        post_a = _make_post(db_session, alice)
        post_b = _make_post(db_session, alice)
        # Alice owns a PAID JUSTIFICATIF on post_a → in her press book.
        _make_purchase(
            db_session,
            user=alice,
            post=post_a,
            amount_cents=200,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )
        # PENDING justificatif on post_b → not in the press book yet.
        _make_purchase(
            db_session,
            user=alice,
            post=post_b,
            amount_cents=100,
            status=PurchaseStatus.PENDING,
            product=PurchaseProduct.JUSTIFICATIF,
        )
        # A CONSULTATION (not a JUSTIFICATIF) doesn't grant a press
        # book entry.
        _make_purchase(
            db_session,
            user=alice,
            post=post_b,
            amount_cents=50,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION,
        )

        rows = list_user_press_book(alice.id)
        ids = {p.id for p in rows}
        assert post_a.id in ids
        assert post_b.id not in ids

    def test_returns_empty_for_missing_user(self):
        assert list_user_press_book(None) == []
        assert list_user_press_book(0) == []

    def test_count_matches_distinct_articles(self, db_session: Session, alice: User):
        post_a = _make_post(db_session, alice)
        post_b = _make_post(db_session, alice)
        # Two PAID JUSTIFICATIFs on post_a (e.g. a re-purchase) must
        # count as ONE Press Book entry.
        _make_purchase(
            db_session,
            user=alice,
            post=post_a,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )
        _make_purchase(
            db_session,
            user=alice,
            post=post_a,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )
        _make_purchase(
            db_session,
            user=alice,
            post=post_b,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )

        assert count_user_press_book(alice.id) == 2


class TestListOrgPressBook:
    def test_aggregates_across_org_members(
        self,
        db_session: Session,
        org: Organisation,
        alice: User,
        bob: User,
        carol: User,
    ):
        """Alice & Bob (both at ACME) each own a JUSTIFICATIF on
        different posts → both appear in ACME's Press Book. Carol
        (other org) doesn't pollute."""
        post_a = _make_post(db_session, alice)
        post_b = _make_post(db_session, alice)
        post_c = _make_post(db_session, alice)
        _make_purchase(
            db_session,
            user=alice,
            post=post_a,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )
        _make_purchase(
            db_session,
            user=bob,
            post=post_b,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )
        _make_purchase(
            db_session,
            user=carol,
            post=post_c,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )

        rows = list_org_press_book(org.id)
        ids = {p.id for p in rows}
        assert post_a.id in ids
        assert post_b.id in ids
        assert post_c.id not in ids, (
            "Carol is at a different org — her Press Book entry must "
            "not leak into ACME's Press Book"
        )
        assert count_org_press_book(org.id) == 2

    def test_de_duplicates_across_members(
        self,
        db_session: Session,
        org: Organisation,
        alice: User,
        bob: User,
    ):
        """Alice and Bob both own a JUSTIFICATIF on the same post →
        the post appears ONCE in the org's Press Book."""
        post = _make_post(db_session, alice)
        for user in (alice, bob):
            _make_purchase(
                db_session,
                user=user,
                post=post,
                amount_cents=1,
                status=PurchaseStatus.PAID,
                product=PurchaseProduct.JUSTIFICATIF,
            )

        rows = list_org_press_book(org.id)
        assert [p.id for p in rows] == [post.id]
        assert count_org_press_book(org.id) == 1

    def test_returns_empty_for_missing_org(self):
        assert list_org_press_book(None) == []
        assert list_org_press_book(0) == []
        assert count_org_press_book(None) == 0
        assert count_org_press_book(0) == 0

    def test_includes_bw_affiliate_justificatif_purchases(
        self,
        db_session: Session,
        org: Organisation,
    ) -> None:
        """A user who is a BW owner or accepted BW member of `org`
        contributes their JUSTIFICATIF purchases to the org's Press Book
        even when their `User.organisation_id` is not set to `org`."""
        # User is NOT a traditional member of `org`.
        user = User(
            email="bw-member@example.com",
            first_name="BW",
            last_name="Member",
            active=True,
        )
        user.organisation_id = None
        db_session.add(user)
        db_session.flush()

        # But user has an accepted role in a BW attached to `org`.
        bw = BusinessWall(
            bw_type="media",
            status="active",
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
            is_free=True,
        )
        db_session.add(bw)
        db_session.flush()
        db_session.add(
            RoleAssignment(
                business_wall_id=bw.id,
                user_id=user.id,
                role_type="BW_OWNER",
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )

        post = _make_post(db_session, user)
        _make_purchase(
            db_session,
            user=user,
            post=post,
            amount_cents=1,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.JUSTIFICATIF,
        )

        rows = list_org_press_book(org.id)
        assert [p.id for p in rows] == [post.id]
        assert count_org_press_book(org.id) == 1


class TestListSalesPerMedia:
    def test_groups_and_sorts_by_total_desc(
        self,
        db_session: Session,
        org: Organisation,
        alice: User,
        carol: User,
    ):
        """ACME (Alice's posts) gets 30 € of sales ; Other Co. (Carol's
        own org's posts) gets 100 €. Order : Other Co. first."""
        other_org = carol.organisation
        alice_post = _make_post(db_session, alice)
        alice_post.publisher_id = org.id
        carol_post = _make_post(db_session, carol)
        carol_post.publisher_id = other_org.id
        db_session.flush()
        _make_purchase(
            db_session,
            user=carol,
            post=alice_post,
            amount_cents=3000,
            status=PurchaseStatus.PAID,
        )
        _make_purchase(
            db_session,
            user=alice,
            post=carol_post,
            amount_cents=10000,
            status=PurchaseStatus.PAID,
        )

        result = list_sales_per_media()

        # Ordered by total desc : Other Co. (100 €) before ACME (30 €).
        org_ids_in_order = [row[0] for row in result]
        totals = {row[0]: row[2] for row in result}
        assert org.id in totals and other_org.id in totals
        assert totals[other_org.id] == 10000
        assert totals[org.id] == 3000
        assert org_ids_in_order.index(other_org.id) < org_ids_in_order.index(org.id)

    def test_excludes_orgs_with_no_paid_sales(
        self, db_session: Session, org: Organisation, alice: User
    ):
        """ACME has only PENDING purchases : it must not appear in the
        recap."""
        alice_post = _make_post(db_session, alice)
        alice_post.publisher_id = org.id
        db_session.flush()
        _make_purchase(
            db_session,
            user=alice,
            post=alice_post,
            amount_cents=1000,
            status=PurchaseStatus.PENDING,
        )

        result = list_sales_per_media()
        assert org.id not in {row[0] for row in result}


class TestListPaidPurchases:
    def test_lists_paid_only_with_flattened_fields(
        self,
        db_session: Session,
        org: Organisation,
        alice: User,
        bob: User,
    ):
        """One row per PAID purchase, with buyer/media/article flattened.
        PENDING and REFUNDED purchases are excluded."""
        media = Organisation(name="Le Média")
        db_session.add(media)
        db_session.flush()
        post = _make_post(db_session, bob)
        post.title = "Mon article"
        post.publisher_id = media.id
        db_session.flush()

        paid = _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=1000,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CESSION,
        )
        paid.paid_at = arrow.get("2026-06-10T10:00:00+00:00")
        paid.currency = "EUR"
        paid.stripe_payment_intent_id = "pi_123"
        _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=999,
            status=PurchaseStatus.PENDING,
        )
        _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=999,
            status=PurchaseStatus.REFUNDED,
        )
        db_session.flush()

        rows = list_paid_purchases()

        assert len(rows) == 1
        row = rows[0]
        assert row.purchase_id == paid.id
        assert row.product_type == "cession"
        assert row.amount_cents == 1000
        assert row.currency == "EUR"
        assert row.buyer_email == "alice@acme.example"
        assert row.buyer_org_name == "ACME Inc."
        assert row.media_org_name == "Le Média"
        assert row.article_id == post.id
        assert row.article_title == "Mon article"
        assert row.stripe_payment_intent_id == "pi_123"

    def test_orders_by_paid_at_desc(self, db_session: Session, alice: User, bob: User):
        post = _make_post(db_session, bob)
        older = _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=100,
            status=PurchaseStatus.PAID,
        )
        older.paid_at = arrow.get("2026-06-01T00:00:00+00:00")
        newer = _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=200,
            status=PurchaseStatus.PAID,
        )
        newer.paid_at = arrow.get("2026-06-09T00:00:00+00:00")
        db_session.flush()

        rows = list_paid_purchases()
        assert [r.purchase_id for r in rows] == [newer.id, older.id]

    def test_since_until_filter_on_paid_at(
        self, db_session: Session, alice: User, bob: User
    ):
        post = _make_post(db_session, bob)
        p_may = _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=1,
            status=PurchaseStatus.PAID,
        )
        p_may.paid_at = arrow.get("2026-05-15T00:00:00+00:00")
        p_jun = _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=1,
            status=PurchaseStatus.PAID,
        )
        p_jun.paid_at = arrow.get("2026-06-15T00:00:00+00:00")
        db_session.flush()

        rows = list_paid_purchases(
            since=arrow.get("2026-06-01T00:00:00+00:00"),
            until=arrow.get("2026-06-30T00:00:00+00:00"),
        )
        assert [r.purchase_id for r in rows] == [p_jun.id]

    def test_blank_names_when_no_org_or_publisher(self, db_session: Session):
        """Buyer with no organisation, article with no publisher → the
        name columns are empty strings, not a crash."""
        loner = User(email="loner@example.com", active=True)
        db_session.add(loner)
        db_session.flush()
        post = _make_post(db_session, loner)  # publisher_id stays None
        paid = _make_purchase(
            db_session,
            user=loner,
            post=post,
            amount_cents=500,
            status=PurchaseStatus.PAID,
        )
        paid.paid_at = arrow.get("2026-06-10T00:00:00+00:00")
        db_session.flush()

        rows = list_paid_purchases()
        assert len(rows) == 1
        assert rows[0].buyer_org_name == ""
        assert rows[0].media_org_name == ""
        assert rows[0].buyer_email == "loner@example.com"

    def test_empty_when_no_paid_purchases(self, db_session: Session):
        assert list_paid_purchases() == []


class TestListPurchasesPerOrg:
    def test_groups_by_buyer_org_and_sorts_desc(
        self,
        db_session: Session,
        org: Organisation,
        alice: User,
        bob: User,
        carol: User,
    ):
        """ACME (Alice + Bob both buyers) spends 80 € ; Other Co.
        (Carol) spends 50 €. Order : ACME first."""
        post = _make_post(db_session, alice)
        _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=5000,
            status=PurchaseStatus.PAID,
        )
        _make_purchase(
            db_session,
            user=bob,
            post=post,
            amount_cents=3000,
            status=PurchaseStatus.PAID,
        )
        _make_purchase(
            db_session,
            user=carol,
            post=post,
            amount_cents=5000,
            status=PurchaseStatus.PAID,
        )

        result = list_purchases_per_org()
        totals = {row[0]: row[2] for row in result}
        assert totals[org.id] == 8000
        assert totals[carol.organisation_id] == 5000
        # Order : ACME (8 000) before Other Co. (5 000).
        org_ids_in_order = [row[0] for row in result]
        assert org_ids_in_order.index(org.id) < org_ids_in_order.index(
            carol.organisation_id
        )


class TestListUserReceivedGifts:
    """Ticket #0227 — list the articles a user was offered (they are the
    beneficiary of a PAID CONSULTATION_GIFT), for the persistent
    WORK/OPPORTUNITÉS rubric."""

    def test_lists_gifted_article_for_beneficiary_only(
        self, db_session: Session, alice: User, bob: User
    ):
        post = _make_post(db_session, alice)
        # Alice (giver) gifts a consultation of `post` to Bob (beneficiary).
        purchase = _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=100,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION_GIFT,
        )
        db_session.add(
            ArticlePurchaseGift(purchase_id=purchase.id, beneficiary_user_id=bob.id)
        )
        db_session.flush()

        # The beneficiary sees the article ; the giver does not.
        assert [p.id for p in list_user_received_gifts(bob.id)] == [post.id]
        assert list_user_received_gifts(alice.id) == []

    def test_pending_gift_is_not_listed(
        self, db_session: Session, alice: User, bob: User
    ):
        post = _make_post(db_session, alice)
        purchase = _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=100,
            status=PurchaseStatus.PENDING,
            product=PurchaseProduct.CONSULTATION_GIFT,
        )
        db_session.add(
            ArticlePurchaseGift(purchase_id=purchase.id, beneficiary_user_id=bob.id)
        )
        db_session.flush()
        assert list_user_received_gifts(bob.id) == []

    def test_expired_gift_is_not_listed(
        self, db_session: Session, alice: User, bob: User
    ):
        """A gift past the consultation window drops off the list (it would
        only lead to a paywall on click — keep the list actionable)."""
        post = _make_post(db_session, alice)
        purchase = _make_purchase(
            db_session,
            user=alice,
            post=post,
            amount_cents=100,
            status=PurchaseStatus.PAID,
            product=PurchaseProduct.CONSULTATION_GIFT,
        )
        # Expire it (coalesce(paid_at, timestamp) prefers paid_at).
        purchase.paid_at = (
            arrow.utcnow().shift(days=-ARTICLE_CONSULTATION_DURATION - 1).datetime
        )
        db_session.add(
            ArticlePurchaseGift(purchase_id=purchase.id, beneficiary_user_id=bob.id)
        )
        db_session.flush()
        assert list_user_received_gifts(bob.id) == []

    def test_none_user_returns_empty(self, db_session: Session):
        assert list_user_received_gifts(None) == []
