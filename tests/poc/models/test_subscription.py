# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Subscription model."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from poc.blueprints.bw_activation_full.models import Subscription, SubscriptionRepository
from poc.blueprints.bw_activation_full.models.subscription import (
    PricingTier,
    SubscriptionStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from poc.blueprints.bw_activation_full.models import BusinessWall


class TestSubscription:
    """Tests for Subscription model."""

    def test_create_subscription(
        self, db_session: Session, paid_business_wall: BusinessWall
    ):
        """Test creating a Subscription."""
        sub = Subscription(
            business_wall_id=paid_business_wall.id,
            status=SubscriptionStatus.PENDING.value,
            pricing_field="client_count",
            pricing_tier=PricingTier.TIER_11_50.value,
            monthly_price=Decimal("299.00"),
            annual_price=Decimal("2990.00"),
            billing_cycle="monthly",
        )
        db_session.add(sub)
        db_session.commit()

        assert sub.id is not None
        assert sub.business_wall_id == paid_business_wall.id
        assert sub.status == SubscriptionStatus.PENDING.value
        assert sub.pricing_field == "client_count"
        assert sub.pricing_tier == PricingTier.TIER_11_50.value
        assert sub.monthly_price == Decimal("299.00")
        assert sub.annual_price == Decimal("2990.00")
        assert sub.billing_cycle == "monthly"

    def test_subscription_repr(self, db_session: Session, paid_business_wall: BusinessWall):
        """Test Subscription __repr__."""
        sub = Subscription(
            business_wall_id=paid_business_wall.id,
            status=SubscriptionStatus.ACTIVE.value,
            pricing_field="client_count",
            pricing_tier=PricingTier.TIER_1_10.value,
            monthly_price=Decimal("99.00"),
            annual_price=Decimal("990.00"),
            billing_cycle="annual",
        )
        db_session.add(sub)
        db_session.commit()

        repr_str = repr(sub)
        assert "Subscription" in repr_str
        assert "active" in repr_str
        assert PricingTier.TIER_1_10.value in repr_str

    def test_subscription_with_billing_address(
        self, db_session: Session, paid_business_wall: BusinessWall
    ):
        """Test Subscription with billing address."""
        sub = Subscription(
            business_wall_id=paid_business_wall.id,
            status=SubscriptionStatus.ACTIVE.value,
            pricing_field="employee_count",
            pricing_tier=PricingTier.TIER_51_200.value,
            monthly_price=Decimal("899.00"),
            annual_price=Decimal("8990.00"),
            billing_cycle="monthly",
            billing_first_name="John",
            billing_last_name="Doe",
            billing_company="Acme Corp",
            billing_address="123 Main St",
            billing_city="Paris",
            billing_zip_code="75001",
            billing_country="France",
        )
        db_session.add(sub)
        db_session.commit()

        assert sub.billing_first_name == "John"
        assert sub.billing_last_name == "Doe"
        assert sub.billing_company == "Acme Corp"
        assert sub.billing_address == "123 Main St"
        assert sub.billing_city == "Paris"
        assert sub.billing_zip_code == "75001"
        assert sub.billing_country == "France"

    def test_subscription_with_stripe_data(
        self, db_session: Session, paid_business_wall: BusinessWall
    ):
        """Test Subscription with Stripe integration data."""
        sub = Subscription(
            business_wall_id=paid_business_wall.id,
            status=SubscriptionStatus.ACTIVE.value,
            pricing_field="client_count",
            pricing_tier=PricingTier.TIER_11_50.value,
            monthly_price=Decimal("299.00"),
            annual_price=Decimal("2990.00"),
            billing_cycle="monthly",
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test456",
            stripe_payment_intent_id="pi_test789",
        )
        db_session.add(sub)
        db_session.commit()

        assert sub.stripe_customer_id == "cus_test123"
        assert sub.stripe_subscription_id == "sub_test456"
        assert sub.stripe_payment_intent_id == "pi_test789"

    def test_subscription_lifecycle(
        self, db_session: Session, paid_business_wall: BusinessWall
    ):
        """Test subscription lifecycle transitions."""
        sub = Subscription(
            business_wall_id=paid_business_wall.id,
            status=SubscriptionStatus.PENDING.value,
            pricing_field="client_count",
            pricing_tier=PricingTier.TIER_1_10.value,
            monthly_price=Decimal("99.00"),
            annual_price=Decimal("990.00"),
            billing_cycle="monthly",
        )
        db_session.add(sub)
        db_session.commit()

        # Activate subscription
        sub.status = SubscriptionStatus.ACTIVE.value
        sub.started_at = datetime.now(timezone.utc)
        db_session.commit()

        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert sub.started_at is not None

        # Cancel subscription
        sub.status = SubscriptionStatus.CANCELLED.value
        sub.cancelled_at = datetime.now(timezone.utc)
        db_session.commit()

        assert sub.status == SubscriptionStatus.CANCELLED.value
        assert sub.cancelled_at is not None

    def test_subscription_pricing_tiers(
        self, db_session: Session, mock_user_id: int
    ):
        """Test all pricing tiers can be created."""
        # Create a business wall for subscriptions
        from poc.blueprints.bw_activation_full.models import BusinessWall

        bw = BusinessWall(
            bw_type="pr",
            status="draft",
            is_free=False,
            owner_id=mock_user_id,
            payer_id=mock_user_id,
        )
        db_session.add(bw)
        db_session.commit()

        tiers = [
            (PricingTier.TIER_1_10, Decimal("99.00"), Decimal("990.00")),
            (PricingTier.TIER_11_50, Decimal("299.00"), Decimal("2990.00")),
            (PricingTier.TIER_51_200, Decimal("899.00"), Decimal("8990.00")),
            (PricingTier.TIER_201_PLUS, Decimal("1999.00"), Decimal("19990.00")),
        ]

        for tier, monthly, annual in tiers:
            sub = Subscription(
                business_wall_id=bw.id,
                status=SubscriptionStatus.PENDING.value,
                pricing_field="client_count",
                pricing_tier=tier.value,
                monthly_price=monthly,
                annual_price=annual,
                billing_cycle="monthly",
            )
            db_session.add(sub)

        db_session.commit()

        count = db_session.query(Subscription).count()
        assert count == len(tiers)


class TestSubscriptionRepository:
    """Tests for SubscriptionRepository."""

    def test_repository_add(
        self, db_session: Session, paid_business_wall: BusinessWall
    ):
        """Test repository add operation."""
        repo = SubscriptionRepository(session=db_session)

        sub = Subscription(
            business_wall_id=paid_business_wall.id,
            status=SubscriptionStatus.PENDING.value,
            pricing_field="client_count",
            pricing_tier=PricingTier.TIER_1_10.value,
            monthly_price=Decimal("99.00"),
            annual_price=Decimal("990.00"),
            billing_cycle="monthly",
        )

        saved_sub = repo.add(sub)

        assert saved_sub.id is not None
        assert saved_sub.pricing_tier == PricingTier.TIER_1_10.value

    def test_repository_get(
        self, db_session: Session, paid_business_wall: BusinessWall
    ):
        """Test repository get operation."""
        repo = SubscriptionRepository(session=db_session)

        sub = Subscription(
            business_wall_id=paid_business_wall.id,
            status=SubscriptionStatus.ACTIVE.value,
            pricing_field="client_count",
            pricing_tier=PricingTier.TIER_11_50.value,
            monthly_price=Decimal("299.00"),
            annual_price=Decimal("2990.00"),
            billing_cycle="monthly",
        )
        repo.add(sub)

        retrieved = repo.get(sub.id)

        assert retrieved is not None
        assert retrieved.id == sub.id
        assert retrieved.pricing_tier == PricingTier.TIER_11_50.value

    def test_repository_update(
        self, db_session: Session, paid_business_wall: BusinessWall
    ):
        """Test repository update operation."""
        repo = SubscriptionRepository(session=db_session)

        sub = Subscription(
            business_wall_id=paid_business_wall.id,
            status=SubscriptionStatus.PENDING.value,
            pricing_field="client_count",
            pricing_tier=PricingTier.TIER_1_10.value,
            monthly_price=Decimal("99.00"),
            annual_price=Decimal("990.00"),
            billing_cycle="monthly",
        )
        repo.add(sub)

        # Update entity attributes
        sub.status = SubscriptionStatus.ACTIVE.value
        updated = repo.update(sub)

        assert updated.status == SubscriptionStatus.ACTIVE.value
