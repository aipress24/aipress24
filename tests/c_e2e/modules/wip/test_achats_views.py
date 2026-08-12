# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0192 / #0193 — `/wip/achats` is the buyer-side view of every
article one-off purchase (CdA / CdAO / JdP / CdD). Lists the purchases
and shows the cumul HT individual + organisationnel that the buy
pop-ups will also use."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PurchaseProduct,
    PurchaseStatus,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User


@pytest.fixture
def post(db_session: Session, test_user: User) -> ArticlePost:
    p = ArticlePost(title="Mon enquête sur les pingouins", owner_id=test_user.id)
    db_session.add(p)
    db_session.flush()
    return p


def _add_paid(
    db_session: Session,
    *,
    user: User,
    post: ArticlePost,
    amount_cents: int,
    product: PurchaseProduct = PurchaseProduct.CONSULTATION,
) -> ArticlePurchase:
    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=user.id,
        product_type=product,
        status=PurchaseStatus.PAID,
        amount_cents=amount_cents,
        paid_at=datetime.now(UTC),
    )
    db_session.add(purchase)
    db_session.flush()
    return purchase


class TestAchatsView:
    def test_page_loads_for_authenticated_user(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        response = logged_in_client.get("/wip/achats")
        assert response.status_code == 200
        assert "achat" in response.data.decode().lower()

    def test_empty_state_when_no_purchases(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        response = logged_in_client.get("/wip/achats")
        body = response.data.decode()
        assert "n'avez pas encore acquis" in body

    def test_lists_paid_purchases_with_amounts_and_titles(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        post: ArticlePost,
    ):
        _add_paid(
            db_session,
            user=test_user,
            post=post,
            amount_cents=1234,
            product=PurchaseProduct.CONSULTATION,
        )
        _add_paid(
            db_session,
            user=test_user,
            post=post,
            amount_cents=5678,
            product=PurchaseProduct.JUSTIFICATIF,
        )

        response = logged_in_client.get("/wip/achats")
        body = response.data.decode()

        assert "Mon enquête sur les pingouins" in body
        assert "12.34" in body, "consultation amount must be displayed"
        assert "56.78" in body, "justificatif amount must be displayed"
        # `Consultation d'article` is HTML-escaped (`d&#39;article`) in
        # the rendered page — match the unambiguous suffix instead.
        assert "Consultation d" in body and "article" in body
        assert "Justificatif de publication" in body

    def test_cumul_individuel_displayed(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        post: ArticlePost,
    ):
        """Erick (#0193) : « Pour l'heure, le cumul de vos achats
        éditoriaux s'élève à [€ XXX HT] ». The same number that goes
        into the buy pop-ups appears at the top of /wip/achats."""
        _add_paid(db_session, user=test_user, post=post, amount_cents=2500)
        _add_paid(db_session, user=test_user, post=post, amount_cents=7500)

        response = logged_in_client.get("/wip/achats")
        body = response.data.decode()
        assert "100.00" in body, "the cumul individuel must show 100.00 €"

    def test_refunded_rows_shown_but_not_in_total(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        post: ArticlePost,
    ):
        _add_paid(db_session, user=test_user, post=post, amount_cents=1000)
        refunded = ArticlePurchase(
            post_id=post.id,
            owner_id=test_user.id,
            product_type=PurchaseProduct.CONSULTATION,
            status=PurchaseStatus.REFUNDED,
            amount_cents=9999,
        )
        db_session.add(refunded)
        db_session.flush()

        response = logged_in_client.get("/wip/achats")
        body = response.data.decode()
        assert "10.00" in body  # only the PAID 1000 cents → 10.00 €
        # the refunded row is displayed but does not pollute the cumul
        assert "99.99" in body
        assert "Remboursé" in body

    def test_pending_rows_not_shown(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        post: ArticlePost,
    ):
        """A Stripe checkout was not finalised (PENDING), must not
        appear in the buyer history."""
        _add_paid(db_session, user=test_user, post=post, amount_cents=1000)
        pending = ArticlePurchase(
            post_id=post.id,
            owner_id=test_user.id,
            product_type=PurchaseProduct.CONSULTATION,
            status=PurchaseStatus.PENDING,
            amount_cents=9999,
        )
        db_session.add(pending)
        db_session.flush()

        response = logged_in_client.get("/wip/achats")
        body = response.data.decode()
        assert "10.00" in body
        assert "99.99" not in body
        assert "En cours" not in body

    def test_anonymous_redirects_to_login(self, client: FlaskClient):
        response = client.get("/wip/achats", follow_redirects=False)
        # The WIP blueprint redirects unauthenticated users to login.
        assert response.status_code in (302, 303, 401)

    def test_purchases_classified_by_month(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        post: ArticlePost,
    ):
        """Purchases are grouped by month with monthly totals and a Details toggle."""
        p1 = ArticlePurchase(
            post_id=post.id,
            owner_id=test_user.id,
            product_type=PurchaseProduct.CONSULTATION,
            status=PurchaseStatus.PAID,
            amount_cents=3000,
            paid_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
        )
        p2 = ArticlePurchase(
            post_id=post.id,
            owner_id=test_user.id,
            product_type=PurchaseProduct.JUSTIFICATIF,
            status=PurchaseStatus.PAID,
            amount_cents=5000,
            paid_at=datetime(2026, 7, 20, 14, 0, tzinfo=UTC),
        )
        db_session.add_all([p1, p2])
        db_session.flush()

        response = logged_in_client.get("/wip/achats")
        body = response.data.decode()

        assert "Août 2026" in body
        assert "Juillet 2026" in body
        assert "30.00" in body
        assert "50.00" in body
        assert "Détails" in body
        assert "Exporter achats éditoriaux" in body
        assert "Exporter achats organisation" in body

    def test_export_user_month_ods(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        post: ArticlePost,
    ):
        """Exporter achats éditoriaux downloads a valid .ods file."""
        p = ArticlePurchase(
            post_id=post.id,
            owner_id=test_user.id,
            product_type=PurchaseProduct.CONSULTATION,
            status=PurchaseStatus.PAID,
            amount_cents=3000,
            paid_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
        )
        db_session.add(p)
        db_session.flush()

        response = logged_in_client.get("/wip/achats/export/user/2026-08.ods")
        assert response.status_code == 200
        assert response.mimetype == "application/vnd.oasis.opendocument.spreadsheet"
        assert response.headers["Content-Disposition"].startswith(
            "attachment; filename=achats_editoriaux_2026-08.ods"
        )
        assert response.data.startswith(b"PK")

    def test_export_org_month_ods(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        post: ArticlePost,
    ):
        """Exporter achats organisation downloads a valid .ods file."""
        p = ArticlePurchase(
            post_id=post.id,
            owner_id=test_user.id,
            product_type=PurchaseProduct.CONSULTATION,
            status=PurchaseStatus.PAID,
            amount_cents=3000,
            paid_at=datetime(2026, 8, 15, 10, 0, tzinfo=UTC),
        )
        db_session.add(p)
        db_session.flush()

        response = logged_in_client.get("/wip/achats/export/org/2026-08.ods")
        assert response.status_code == 200
        assert response.mimetype == "application/vnd.oasis.opendocument.spreadsheet"
        assert response.headers["Content-Disposition"].startswith(
            "attachment; filename=achats_organisation_2026-08.ods"
        )
        assert response.data.startswith(b"PK")
