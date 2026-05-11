# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Local mirror of Stripe Price objects.

Populated by webhooks `price.created`, `price.updated`, `price.deleted`
and by the CLI bootstrap `flask stripe sync prices`. Consumed by the
display helper `stripe_price_display` so templates never call Stripe at
render time. Spec: local-notes/specs/finances.md §4.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.flask.util import utcnow
from app.models.base import Base


class StripePrice(Base):
    """Mirror of a Stripe Price object.

    The `id` column is the Stripe price id (e.g. `price_1AbcXYZ`) used as
    primary key. `active=False` rows are kept for traceability — never
    DELETE.
    """

    __tablename__ = "stripe_price"

    id: Mapped[str] = mapped_column(primary_key=True)
    product_id: Mapped[str] = mapped_column(index=True)
    unit_amount_cents: Mapped[int]
    currency: Mapped[str]  # "eur"
    active: Mapped[bool] = mapped_column(default=True, index=True)
    tax_behavior: Mapped[str]  # "inclusive" | "exclusive" | "unspecified"
    nickname: Mapped[str | None] = mapped_column(default=None)
    recurring_interval: Mapped[str | None] = mapped_column(default=None)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    synced_at: Mapped[datetime] = mapped_column(default=utcnow)

    def __repr__(self) -> str:
        return (
            f"<StripePrice {self.id} {self.unit_amount_cents}{self.currency} "
            f"active={self.active}>"
        )
