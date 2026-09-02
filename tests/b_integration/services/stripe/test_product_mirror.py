# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The product mirror: sync, drift, and the shape price selection reads.

The twin of `test_prices_sync.py`, at the same tier and for the same
reason — the local half lives in the database.

The last class is the point of the whole table: `_price_id_for` must
resolve a price without touching Stripe, because it runs on the article
render path for every reader who has not bought
(`notes/lessons-learned.md` §"Never hit the Stripe API at render time").
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
import stripe

from app.modules.wire.models import PurchaseProduct
from app.modules.wire.views import purchase
from app.modules.wire.views.purchase import _price_id_for
from app.services.stripe._price_model import StripePrice
from app.services.stripe._product_model import StripeProduct
from app.services.stripe.product_mirror import (
    active_products,
    list_product_drifts,
    sync_all_products,
)
from tests.a_unit.services.stripe._fake_client import FakeStripeClient, stripe_obj

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def _clean_mirrors(db_session: Session):
    """`sync_all_products` commits — correctly, it is a CLI/cron entry
    point — so the savepoint the `db_session` fixture wraps each test in
    cannot roll it back. Clear both mirrors on both sides of every test:
    other files commit to these tables too.
    """
    _wipe(db_session)
    yield
    _wipe(db_session)


def _wipe(db_session: Session) -> None:
    db_session.query(StripeProduct).delete()
    db_session.query(StripePrice).delete()
    db_session.commit()


CONSULTATION_TAXO = {
    "domain": "consultation",
    "family": "article",
    "offer": "paid",
}


def _stripe_product(
    *,
    product_id: str = "prod_consultation",
    name: str = "Consultation",
    active: bool = True,
    default_price: object = "price_consultation",
    metadata: dict | None = None,
) -> SimpleNamespace:
    return stripe_obj(
        id=product_id,
        name=name,
        active=active,
        default_price=default_price,
        metadata=CONSULTATION_TAXO if metadata is None else metadata,
    )


def _mirror(db_session: Session, **fields) -> StripeProduct:
    base = {
        "id": "prod_consultation",
        "name": "Consultation",
        "active": True,
        "default_price_id": "price_consultation",
        "metadata_json": dict(CONSULTATION_TAXO),
    }
    product = StripeProduct(**{**base, **fields})
    db_session.add(product)
    db_session.flush()
    return product


def _synced_at(db_session: Session) -> datetime:
    db_session.expire_all()
    return db_session.get(StripeProduct, "prod_consultation").synced_at


class TestSync:
    def test_pulls_products_into_the_mirror(self, db_session: Session) -> None:
        client = FakeStripeClient(product_listing=[_stripe_product()])

        count = sync_all_products(client=client)

        assert count == 1
        row = db_session.get(StripeProduct, "prod_consultation")
        assert row is not None
        assert row.metadata_json == CONSULTATION_TAXO

    def test_is_idempotent(self, db_session: Session) -> None:
        """The hourly actor re-runs this every hour; it must not duplicate."""
        client = FakeStripeClient(product_listing=[_stripe_product()])

        sync_all_products(client=client)
        sync_all_products(client=FakeStripeClient(product_listing=[_stripe_product()]))

        rows = db_session.query(StripeProduct).all()
        assert len(rows) == 1

    def test_a_metadata_change_is_carried_over(self, db_session: Session) -> None:
        """This is the repair path: a dropped `product.updated` webhook
        leaves stale taxonomy, and the next sync fixes it."""
        _mirror(db_session, metadata_json={"domain": "stale"})

        sync_all_products(client=FakeStripeClient(product_listing=[_stripe_product()]))

        assert db_session.get(StripeProduct, "prod_consultation").metadata_json == (
            CONSULTATION_TAXO
        )

    def test_resync_moves_synced_at(self, db_session: Session) -> None:
        """The hourly actor is what makes this column readable: without
        it `synced_at` would say when the row was first seen."""
        _mirror(db_session, synced_at=datetime(2020, 1, 1, tzinfo=UTC))
        before = _synced_at(db_session)

        sync_all_products(client=FakeStripeClient(product_listing=[_stripe_product()]))

        # Read both ends back from the database: the column is naive on
        # SQLite and aware on PostgreSQL, and the two do not compare.
        assert _synced_at(db_session) > before


class TestDrift:
    def test_no_drift_when_they_agree(self, db_session: Session) -> None:
        _mirror(db_session)

        drifts = list_product_drifts(
            client=FakeStripeClient(product_listing=[_stripe_product()])
        )

        assert drifts == []

    def test_a_product_missing_locally(self, db_session: Session) -> None:
        drifts = list_product_drifts(
            client=FakeStripeClient(product_listing=[_stripe_product()])
        )

        assert [(d.product_id, d.field) for d in drifts] == [
            ("prod_consultation", "presence")
        ]

    def test_stale_taxonomy_is_reported(self, db_session: Session) -> None:
        """The drift that silently breaks buying."""
        _mirror(db_session, metadata_json={"domain": "certificate"})

        drifts = list_product_drifts(
            client=FakeStripeClient(product_listing=[_stripe_product()])
        )

        assert [d.field for d in drifts] == ["metadata_json"]

    def test_a_local_row_stripe_no_longer_lists(self, db_session: Session) -> None:
        _mirror(db_session, id="prod_gone")

        drifts = list_product_drifts(client=FakeStripeClient(product_listing=[]))

        assert [(d.product_id, d.field) for d in drifts] == [("prod_gone", "active")]


class TestTheShapePriceSelectionReads:
    def test_exposes_metadata_and_default_price(self, db_session: Session) -> None:
        _mirror(db_session)

        [product] = active_products()

        assert product.metadata == CONSULTATION_TAXO
        assert product.default_price == "price_consultation"

    def test_inactive_products_are_left_out(self, db_session: Session) -> None:
        _mirror(db_session, active=False)

        assert active_products() == []

    def test_falls_back_to_the_price_mirror(self, db_session: Session) -> None:
        """Stripe reported no default price, so `resolve_product_price`
        would have called `Price.list`. The price mirror answers instead."""
        _mirror(db_session, default_price_id=None)
        db_session.add(
            StripePrice(
                id="price_from_mirror",
                product_id="prod_consultation",
                unit_amount_cents=350,
                currency="eur",
                active=True,
                tax_behavior="exclusive",
            )
        )
        db_session.flush()

        [product] = active_products()

        assert product.default_price == "price_from_mirror"


class TestPriceIdForReadsTheMirror:
    """`_price_id_for` is called while rendering an article, so it
    resolves from the mirror and never from Stripe. These cases were a
    unit-tier class driving a `FakeStripeClient` through a `client=`
    argument that only tests ever passed; the argument is gone and the
    behaviour is pinned here, against the path production runs.
    """

    @pytest.fixture(autouse=True)
    def _no_stripe_calls(self, monkeypatch) -> None:
        """The fence the previous implementation would have failed.

        `_select_price_id` used to resolve each candidate through
        `resolve_product_price`, which reaches for `Price.retrieve`
        whenever `default_price` is a bare id — which the mirror's
        always is. So every render paid for an HTTP round-trip whose
        result was thrown away, and because `resolve_product_price`
        swallows `StripeError`, the tests still passed. `AssertionError`
        is not a `StripeError`, so this one cannot be swallowed.
        """

        def boom(*_args, **_kwargs):
            msg = "Stripe API called while resolving a price for display"
            raise AssertionError(msg)

        monkeypatch.setattr(stripe.Price, "retrieve", boom)
        monkeypatch.setattr(stripe.Price, "list", boom)
        monkeypatch.setattr(stripe.Product, "list", boom)

    def test_the_render_path_imports_no_catalogue_fetcher(self) -> None:
        """The structural half of the rule. `from ... import` binds at
        import time, so monkeypatching cannot catch a reintroduced call
        — pin the absence of the symbol instead."""
        assert not hasattr(purchase, "fetch_stripe_product_list")

    def test_resolves_the_price_from_the_mirror(self, db_session: Session) -> None:
        _mirror(db_session)

        assert _price_id_for(PurchaseProduct.CONSULTATION, genre="") == (
            "price_consultation"
        )

    def test_a_genre_specific_product_wins(self, db_session: Session) -> None:
        _mirror(db_session, id="prod_generic", default_price_id="p_generic")
        _mirror(
            db_session,
            id="prod_enquete",
            default_price_id="p_enquete",
            metadata_json={**CONSULTATION_TAXO, "genre": "survey"},
        )

        assert _price_id_for(PurchaseProduct.CONSULTATION, genre="Enquête") == (
            "p_enquete"
        )

    def test_falls_back_to_the_generic_product(self, db_session: Session) -> None:
        """A genre with no dedicated product still resolves."""
        _mirror(db_session, id="prod_generic", default_price_id="p_generic")

        assert _price_id_for(PurchaseProduct.CONSULTATION, genre="Interview") == (
            "p_generic"
        )

    def test_an_empty_mirror_yields_no_price_rather_than_a_call(self) -> None:
        """Before the first sync the page shows no amount — it does not
        fall back to the network. The caller flashes « Produit
        momentanément indisponible »."""
        assert _price_id_for(PurchaseProduct.CONSULTATION, genre="") == ""

    def test_unrelated_products_yield_no_price(self, db_session: Session) -> None:
        """Pin that the family scan does not match a product carrying
        someone else's taxonomy."""
        _mirror(db_session, id="prod_other", metadata_json={"other": "x"})

        assert _price_id_for(PurchaseProduct.CONSULTATION, genre="") == ""
