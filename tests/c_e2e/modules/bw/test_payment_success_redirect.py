# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for `/BW/payment-success/<bw_type>` post-checkout redirect."""

from __future__ import annotations

from uuid import uuid4

import stripe

from app.enums import BWStatus, BWType
from app.flask.extensions import db
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    Subscription,
    SubscriptionStatus,
)


def _create_user_with_draft_bw(bw_type: str = BWType.UNION.value):
    suffix = uuid4().hex[:8]
    user = User(
        email=f"union-payer-{suffix}@example.com",
        first_name="Union",
        last_name="Payer",
        active=True,
    )
    db.session.add(user)
    db.session.flush()

    org = Organisation(name=f"Asso {suffix}")
    db.session.add(org)
    db.session.flush()
    user.organisation_id = org.id

    bw = BusinessWall(
        bw_type=bw_type,
        status=BWStatus.DRAFT.value,
        is_free=False,
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=org.id,
        payer_email=user.email,
    )
    db.session.add(bw)
    db.session.flush()

    sub = Subscription(
        business_wall_id=bw.id,
        status=SubscriptionStatus.PENDING.value,
        pricing_field="stripe",
        pricing_tier="via_pricing_table",
        monthly_price=0,
        annual_price=0,
    )
    db.session.add(sub)
    db.session.commit()
    return user, org, bw


def test_payment_success_activates_draft_bw_and_redirects_to_dashboard(
    app, client, monkeypatch
) -> None:
    """When Stripe redirects with `?session_id=...` before the webhook
    arrives, `payment_success` activates the DRAFT BW and redirects to
    `/BW/dashboard` instead of leaving the user in `/BW/confirm-subscription`.
    """
    with app.app_context():
        user, org, bw = _create_user_with_draft_bw(BWType.UNION.value)
        bw_id = bw.id
        org_id = org.id
        user_fs_uniquifier = user.fs_uniquifier

    with client.session_transaction() as sess:
        sess["_user_id"] = user_fs_uniquifier

    monkeypatch.setattr(
        "app.modules.bw.bw_activation.routes.stage3.load_stripe_api_key",
        lambda: True,
    )
    monkeypatch.setattr(
        stripe.checkout.Session,
        "retrieve",
        staticmethod(
            lambda sid: {
                "id": sid,
                "mode": "subscription",
                "status": "complete",
                "payment_status": "paid",
                "client_reference_id": str(bw_id),
                "customer": "cus_test_union",
                "subscription": "sub_test_union",
                "metadata": {"bw_id": str(bw_id)},
            }
        ),
    )

    response = client.get(
        "/BW/payment-success/union?session_id=cs_test_union_123",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/BW/dashboard")

    with app.app_context():
        refreshed_bw = db.session.get(BusinessWall, bw_id)
        refreshed_org = db.session.get(Organisation, org_id)
        assert refreshed_bw is not None
        assert refreshed_bw.status == BWStatus.ACTIVE.value
        assert refreshed_org is not None
        assert refreshed_org.bw_id == bw_id
        assert refreshed_org.bw_active == BWType.UNION.value


def test_payment_success_without_session_id_renders_waiting_page(app, client) -> None:
    """Without a `session_id` (and before webhook), renders payment_success.html."""
    with app.app_context():
        user, _org, _bw = _create_user_with_draft_bw(BWType.UNION.value)
        user_fs_uniquifier = user.fs_uniquifier

    with client.session_transaction() as sess:
        sess["_user_id"] = user_fs_uniquifier

    response = client.get("/BW/payment-success/union", follow_redirects=False)

    assert response.status_code == 200
    assert "Paiement réussi" in response.get_data(as_text=True)
