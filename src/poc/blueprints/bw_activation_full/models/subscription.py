# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Subscription and pricing models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types import GUID
from sqlalchemy import DECIMAL, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .business_wall import BusinessWallPoc


class SubscriptionStatus(StrEnum):
    """Subscription status."""

    PENDING = "pending"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PricingTier(StrEnum):
    """Pricing tiers based on client/employee count."""

    TIER_1_10 = "1-10"
    TIER_11_50 = "11-50"
    TIER_51_200 = "51-200"
    TIER_201_PLUS = "201+"


class SubscriptionPoc(UUIDAuditBase):
    """Subscription for paid Business Walls.

    Tracks pricing information, payment status, and Stripe integration.
    """

    __tablename__ = "poc_subscription"

    # Foreign key to BusinessWall
    business_wall_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("poc_business_wall.id", ondelete="CASCADE"), nullable=False
    )
    business_wall: Mapped[BusinessWallPoc] = relationship(back_populates="subscription")

    # Subscription status
    status: Mapped[str] = mapped_column(
        String(20), default=SubscriptionStatus.PENDING.value
    )

    # Pricing information
    pricing_field: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "client_count" or "employee_count"
    pricing_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    monthly_price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    annual_price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    billing_cycle: Mapped[str] = mapped_column(
        String(10), default="monthly"
    )  # "monthly" or "annual"

    # Payment tracking
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    # Subscription period
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Billing address (stored as JSON-compatible fields)
    billing_first_name: Mapped[str] = mapped_column(String(100), default="")
    billing_last_name: Mapped[str] = mapped_column(String(100), default="")
    billing_company: Mapped[str] = mapped_column(String(200), default="")
    billing_address: Mapped[str] = mapped_column(String(500), default="")
    billing_city: Mapped[str] = mapped_column(String(100), default="")
    billing_zip_code: Mapped[str] = mapped_column(String(20), default="")
    billing_country: Mapped[str] = mapped_column(String(100), default="")

    def __repr__(self) -> str:
        return (
            f"<SubscriptionPoc {self.id} status={self.status} tier={self.pricing_tier}>"
        )
