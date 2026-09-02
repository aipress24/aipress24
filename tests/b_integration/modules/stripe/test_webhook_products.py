# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for the `product.*` webhook handlers.

The twin of `test_webhook_prices.py`. This is the mirror's *primary*
channel — the hourly actor only repairs what these missed — so what it
writes has to be right, and the taxonomy in `metadata` is the part that
decides which product serves a purchase.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from app.modules.stripe.views import webhook
from app.modules.stripe.views.webhook import (
    _EVENT_HANDLER_NAMES,
    on_product_created,
    on_product_deleted,
    on_product_updated,
    resolve_handler,
)
from app.services.stripe._product_model import StripeProduct

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

TAXONOMY = {"domain": "consultation", "family": "article", "offer": "paid"}


@pytest.fixture(autouse=True)
def _clean_products(db_session: Session):
    """The handlers commit — correctly, they are the view layer — so the
    savepoint wrapping each test cannot roll them back."""
    yield
    db_session.query(StripeProduct).delete()
    db_session.commit()


def _product_event(event_type: str, **overrides):
    payload = {
        "id": "prod_test_xyz",
        "name": "Consultation d'article",
        "active": True,
        "default_price": "price_test_xyz",
        "metadata": dict(TAXONOMY),
    }
    payload.update(overrides)
    return SimpleNamespace(
        id=f"evt_{event_type}",
        type=event_type,
        data=SimpleNamespace(object=payload),
    )


class TestProductWebhookHandlers:
    def test_product_created_inserts_row(self, db_session: Session) -> None:
        on_product_created(_product_event("product.created"))

        fetched = db_session.get(StripeProduct, "prod_test_xyz")
        assert fetched is not None
        assert fetched.name == "Consultation d'article"
        assert fetched.default_price_id == "price_test_xyz"
        assert fetched.active is True

    def test_the_taxonomy_arrives_intact(self, db_session: Session) -> None:
        """`_select_price_id` filters on exactly these keys."""
        on_product_created(_product_event("product.created"))

        assert db_session.get(StripeProduct, "prod_test_xyz").metadata_json == TAXONOMY

    def test_product_updated_overwrites_the_taxonomy(self, db_session: Session) -> None:
        """The event an admin editing metadata in the Stripe dashboard
        generates, and the reason the mirror can be trusted."""
        on_product_created(_product_event("product.created"))
        on_product_updated(
            _product_event("product.updated", metadata={"domain": "license"})
        )

        fetched = db_session.get(StripeProduct, "prod_test_xyz")
        assert fetched.metadata_json == {"domain": "license"}

    def test_product_deleted_marks_inactive(self, db_session: Session) -> None:
        """Stripe reports `active=true` on the deleted object; the row
        must go inactive anyway, and must not be deleted."""
        on_product_created(_product_event("product.created"))
        on_product_deleted(_product_event("product.deleted", active=True))

        fetched = db_session.get(StripeProduct, "prod_test_xyz")
        assert fetched is not None
        assert fetched.active is False

    def test_idempotent_replay(self, db_session: Session) -> None:
        """Stripe retries; three deliveries are still one row."""
        for _ in range(3):
            on_product_created(_product_event("product.created"))

        rows = db_session.query(StripeProduct).filter_by(id="prod_test_xyz").all()
        assert len(rows) == 1


class TestTheDispatchMap:
    """Wiring, not behaviour: the handlers above are useless if Stripe's
    event never reaches them."""

    @pytest.mark.parametrize(
        ("event_type", "handler_name"),
        [
            ("product.created", "on_product_created"),
            ("product.updated", "on_product_updated"),
            ("product.deleted", "on_product_deleted"),
        ],
    )
    def test_product_events_are_routed(self, event_type, handler_name) -> None:
        assert resolve_handler(event_type) == handler_name

    def test_every_registered_handler_exists(self) -> None:
        """Deliberately map-wide, not product-only: dispatch is
        `globals()[name]` on a hand-written string, so a typo in any
        entry is a `KeyError` in production and nowhere else."""
        missing = [
            name
            for name in _EVENT_HANDLER_NAMES.values()
            if not callable(getattr(webhook, name, None))
        ]

        assert missing == []
