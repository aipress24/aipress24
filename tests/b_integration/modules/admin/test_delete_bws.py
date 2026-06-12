# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for admin delete-bws view."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.views.delete_bws import (
    _cancel_stripe_subscriptions,
    _remove_all_bw,
)
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.models.subscription import Subscription


class TestRemoveAllBw:
    """Test suite for the _remove_all_bw helper."""

    def test_remove_all_bw_deletes_records(self, db_session):
        """_remove_all_bw deletes all BusinessWalls and clears org fields."""
        org = Organisation(name="Test Org")
        user = User(email="test@example.com", organisation=org)
        db_session.add_all([org, user])
        db_session.flush()

        bw = BusinessWall(
            bw_type="media",
            status=BWStatus.ACTIVE.value,
            owner_id=int(user.id),
            payer_id=int(user.id),
            organisation_id=int(org.id),
            name="Test BW",
        )
        db_session.add(bw)
        org.bw_id = bw.id
        org.bw_active = "media"
        org.bw_name = "Test BW"
        db_session.commit()

        try:
            deleted_count = _remove_all_bw()

            assert deleted_count == 1
            assert db_session.query(BusinessWall).count() == 0
            assert user.selected_bw_id is None
            assert org.bw_id is None
            assert org.bw_active is None
            assert org.bw_name == ""
        finally:
            # _remove_all_bw commits; clean up the test user/org explicitly.
            db_session.delete(user)
            db_session.delete(org)
            db_session.commit()

    def test_remove_all_bw_no_records(self, db_session):
        """_remove_all_bw is a no-op when no BusinessWalls exist."""
        assert db_session.query(BusinessWall).count() == 0
        deleted_count = _remove_all_bw()
        assert deleted_count == 0


class TestCancelStripeSubscriptions:
    """Test suite for Stripe subscription cancellation."""

    def test_cancel_stripe_subscriptions_skips_without_key(self, db_session, app):
        """When no Stripe key is configured, cancellation is skipped gracefully."""
        app.config["STRIPE_SECRET_KEY"] = None
        org = Organisation(name="Stripe Org")
        user = User(email="stripe@example.com", organisation=org)
        db_session.add_all([org, user])
        db_session.flush()

        bw = BusinessWall(
            bw_type="media",
            status=BWStatus.ACTIVE.value,
            owner_id=int(user.id),
            payer_id=int(user.id),
            organisation_id=int(org.id),
            name="Stripe BW",
        )
        db_session.add(bw)
        db_session.flush()

        sub = Subscription(
            business_wall_id=bw.id,
            status="active",
            pricing_field="stripe",
            pricing_tier="via_pricing_table",
            monthly_price=0,
            annual_price=0,
            stripe_subscription_id="sub_test_123",
        )
        db_session.add(sub)
        db_session.commit()

        try:
            cancelled = _cancel_stripe_subscriptions()
            assert cancelled == 0
        finally:
            db_session.delete(sub)
            db_session.delete(bw)
            db_session.delete(user)
            db_session.delete(org)
            db_session.commit()

    def test_cancel_stripe_subscriptions_calls_stripe(self, db_session, app):
        """When Stripe is configured, it cancels linked subscriptions."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_dummy"
        org = Organisation(name="Stripe Org")
        user = User(email="stripe@example.com", organisation=org)
        db_session.add_all([org, user])
        db_session.flush()

        bw = BusinessWall(
            bw_type="media",
            status=BWStatus.ACTIVE.value,
            owner_id=int(user.id),
            payer_id=int(user.id),
            organisation_id=int(org.id),
            name="Stripe BW",
        )
        db_session.add(bw)
        db_session.flush()

        sub = Subscription(
            business_wall_id=bw.id,
            status="active",
            pricing_field="stripe",
            pricing_tier="via_pricing_table",
            monthly_price=0,
            annual_price=0,
            stripe_subscription_id="sub_test_456",
        )
        db_session.add(sub)
        db_session.commit()

        try:
            with patch("app.modules.admin.views.delete_bws.stripe") as mock_stripe:
                mock_stripe.Subscription = MagicMock()
                mock_stripe.Subscription.delete = MagicMock(
                    return_value={"id": "sub_test_456"}
                )
                cancelled = _cancel_stripe_subscriptions()
                assert cancelled == 1
                mock_stripe.Subscription.delete.assert_called_once_with("sub_test_456")
        finally:
            db_session.delete(sub)
            db_session.delete(bw)
            db_session.delete(user)
            db_session.delete(org)
            db_session.commit()
