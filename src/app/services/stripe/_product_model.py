# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Local mirror of Stripe Product objects.

The twin of `_price_model.StripePrice`, and populated the same three
ways: webhooks `product.created`, `product.updated`, `product.deleted`,
the CLI bootstrap `flask stripe sync products`, and the hourly catch-up
actor.

It exists because the taxonomy that decides *which* product serves a
purchase — `domain` / `family` / `offer` / `genre` — lives in the
product's metadata, not the price's. Without this table, resolving a
price id meant listing every Stripe product on the request path; the
article page did exactly that on every render for a non-buyer.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.flask.util import utcnow
from app.models.base import Base


class StripeProduct(Base):
    """Mirror of a Stripe Product object.

    The `id` column is the Stripe product id (e.g. `prod_1AbcXYZ`) used
    as primary key. `active=False` rows are kept for traceability —
    never DELETE, same rule as `StripePrice`.
    """

    __tablename__ = "stripe_product"

    id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(default="")
    active: Mapped[bool] = mapped_column(default=True, index=True)
    #: The default price id Stripe reports, when it has one. The
    #: authoritative amount still comes from `stripe_price`.
    default_price_id: Mapped[str | None] = mapped_column(default=None, index=True)
    #: The taxonomy: `domain`, `family`, `offer`, `genre`. This is what
    #: product selection filters on.
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    #: `utcnow()` is timezone-aware, so the column must be too — a bare
    #: `Mapped[datetime]` maps to a naive `timestamp` and silently drops
    #: the offset on PostgreSQL.
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def __repr__(self) -> str:
        return f"<StripeProduct {self.id} {self.name!r} active={self.active}>"
