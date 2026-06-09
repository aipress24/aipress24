# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests pinning the *shape* of the `StripePrice` SQLAlchemy mapped
class at `app.services.stripe._price_model`.

These tests do NOT touch a database. They introspect SQLAlchemy
metadata to lock in the columns / defaults / index choices that the
rest of the Stripe integration depends on :

- `__tablename__ = "stripe_price"` — referenced by Alembic migrations
  and (potentially) raw SQL in finance dashboards.
- The `id` column is the *Stripe* price id (e.g. `price_1AbcXYZ`) used
  as PRIMARY KEY — the docstring says so, and `webhook` / `prices.py`
  call `db_session.get(StripePrice, "price_…")` relying on it.
- `product_id` and `active` are indexed — every dashboard query filters
  on « active prices for product X », so dropping the index would tank
  page load times.
- The default of `active=True` — newly mirrored prices land active.
  A regression flipping it to `False` would silently hide every new
  price from the pricing table.
- `metadata_json` defaults to `dict` (NOT `None`) — downstream
  templates do `price.metadata_json.get(...)` and `None.get` would
  500 the pricing page.
- `synced_at` defaults to `utcnow` — used by `reconciliation.py` to
  detect stale mirrors. If the default disappears, every webhook
  insert would crash on a NOT NULL violation.
- `nickname` and `recurring_interval` ARE nullable — the source comment
  says one-shot prices have no `recurring_interval`, and many prices
  have no nickname. Pin so a refactor doesn't accidentally make them
  required.
- The `__repr__` shape — read in log lines and the debug toolbar when
  triaging « why is price X not showing ? » bugs.

DB-bound behaviour (defaults firing on INSERT, index actually being
hit by the query planner) belongs in `b_integration` tests, not here.
Spec reference: `local-notes/specs/finances.md` §4.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

import pytest
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    String,
    inspect as sa_inspect,
)

from app.flask.util import utcnow
from app.models.base import Base
from app.services.stripe._price_model import StripePrice


def _column(model, name):
    """Fetch a column from a mapped class without instantiating a row."""
    return model.__table__.columns[name]


class TestStripePriceClassShape:
    """Top-level wiring of the mapped class.

    These tests catch « somebody changed the base class », « somebody
    renamed the table », « somebody dropped the `Mapped` annotations »
    — three regressions that would each break the Stripe sync at
    different layers."""

    def test_inherits_from_base(self):
        """Pin the parent so a refactor to a different declarative base
        catches here, not at first `db.create_all()`."""
        assert issubclass(StripePrice, Base)

    def test_tablename(self):
        """Hard-coded `__tablename__` is referenced by Alembic
        migrations. Renaming it without a migration would silently
        break every SELECT."""
        assert StripePrice.__tablename__ == "stripe_price"

    def test_is_sqlalchemy_mapped(self):
        """`sa_inspect` succeeds only on mapped classes — a defensive
        gate against the class accidentally losing its `Mapped`
        annotations."""
        mapper = sa_inspect(StripePrice)
        assert mapper is not None
        assert mapper.class_ is StripePrice

    def test_no_custom_table_args(self):
        """At the time of writing there are NO composite unique
        constraints or `__table_args__` declared. Pin the absence so
        adding one (e.g. UNIQUE on `(product_id, currency, …)`) is a
        deliberate, reviewed change — such a constraint would interact
        with the Stripe webhook upsert flow."""
        assert getattr(StripePrice, "__table_args__", None) is None


class TestStripePriceColumns:
    """The column set is the table's contract with the rest of the
    codebase. Pin it explicitly — `prices.py`, `webhook.py`, and
    `reconciliation.py` all read these columns by name."""

    EXPECTED_COLUMNS: ClassVar[set[str]] = {
        "id",
        "product_id",
        "unit_amount_cents",
        "currency",
        "active",
        "tax_behavior",
        "nickname",
        "recurring_interval",
        "metadata_json",
        "synced_at",
    }

    def test_expected_columns_all_present(self):
        """Every name the Stripe integration reads must exist."""
        actual = set(StripePrice.__table__.columns.keys())
        missing = self.EXPECTED_COLUMNS - actual
        assert not missing, f"Missing columns on StripePrice: {missing}"

    def test_no_unexpected_columns(self):
        """Pin the exact set — extra columns sneaking in (e.g. a
        forgotten debug field, a stray FK) would be visible here.
        This file is tiny and stable; a strict equality is fine."""
        actual = set(StripePrice.__table__.columns.keys())
        extra = actual - self.EXPECTED_COLUMNS
        assert not extra, f"Unexpected columns on StripePrice: {extra}"

    @pytest.mark.parametrize(
        "col_name",
        [
            "id",
            "product_id",
            "unit_amount_cents",
            "currency",
            "active",
            "tax_behavior",
            "metadata_json",
            "synced_at",
        ],
    )
    def test_core_columns_are_not_nullable(self, col_name):
        """Every column that describes « what this price is » must be
        NOT NULL — a `StripePrice` row without an amount, a currency,
        or a `tax_behavior` is meaningless to the pricing table."""
        assert _column(StripePrice, col_name).nullable is False

    @pytest.mark.parametrize(
        "col_name",
        ["nickname", "recurring_interval"],
    )
    def test_optional_columns_are_nullable(self, col_name):
        """`nickname` is the human label and many prices have none.
        `recurring_interval` is null for one-shot (non-subscription)
        prices. Both MUST stay nullable — making them required would
        break webhook ingestion for a large fraction of real prices."""
        assert _column(StripePrice, col_name).nullable is True


class TestPrimaryKeyAndIndexes:
    """The `id` column is the Stripe price id used directly as PK, and
    `product_id` / `active` are indexed because every dashboard query
    filters on them. Pin both — dropping the indexes would silently
    regress pricing-page latency."""

    def test_id_is_primary_key(self):
        """The Stripe price id (`price_…`) is the PK. `db_session.get(
        StripePrice, "price_…")` relies on this."""
        col = _column(StripePrice, "id")
        assert col.primary_key is True

    def test_id_is_string_type(self):
        """Stripe ids are opaque strings (`price_1AbcXYZ…`), never
        integers. Pin to catch a refactor that swaps to autoincrement
        — that would silently break every webhook insert."""
        col = _column(StripePrice, "id")
        assert isinstance(col.type, String)

    def test_product_id_is_indexed(self):
        """Every « prices for product X » lookup hits this index."""
        col = _column(StripePrice, "product_id")
        assert col.index is True

    def test_active_is_indexed(self):
        """The pricing table filters on `active=True`. Pin the index
        so dropping it (very tempting in a « cleanup » PR) is a
        deliberate decision."""
        col = _column(StripePrice, "active")
        assert col.index is True

    def test_product_id_has_no_foreign_key(self):
        """`product_id` is a plain string mirroring the Stripe product
        id — there is intentionally no FK to a local `stripe_product`
        table (webhooks may arrive in any order, and we don't want
        price ingestion to fail because the product webhook is late).
        Pin so adding an FK is a deliberate migration."""
        col = _column(StripePrice, "product_id")
        assert list(col.foreign_keys) == []


class TestColumnTypes:
    """Pin the SQLAlchemy column types — a refactor to `Numeric` for
    `unit_amount_cents` (a classic Stripe footgun) or to `String` for
    `active` would silently break the price display helper."""

    @pytest.mark.parametrize(
        ("col_name", "expected_type"),
        [
            ("id", String),
            ("product_id", String),
            ("unit_amount_cents", Integer),
            ("currency", String),
            ("active", Boolean),
            ("tax_behavior", String),
            ("nickname", String),
            ("recurring_interval", String),
            ("metadata_json", JSON),
            ("synced_at", DateTime),
        ],
    )
    def test_column_type(self, col_name, expected_type):
        col = _column(StripePrice, col_name)
        assert isinstance(col.type, expected_type), (
            f"{col_name} expected {expected_type.__name__}, "
            f"got {type(col.type).__name__}"
        )

    def test_unit_amount_is_integer_not_numeric(self):
        """Stripe amounts are integer cents — never floats / Decimals.
        Pin so a refactor to `Numeric` (a classic « let's make this
        more precise » mistake) is flagged before it ships."""
        col = _column(StripePrice, "unit_amount_cents")
        assert isinstance(col.type, Integer)


class TestDefaults:
    """The column defaults are the lynchpins of the webhook ingestion
    flow. Each one prevents a specific class of regression."""

    def test_active_defaults_to_true(self):
        """New rows land active. Flipping to `False` would silently
        hide every new price from the pricing table — exactly the
        kind of regression a one-line change can cause."""
        col = _column(StripePrice, "active")
        assert col.default is not None
        assert col.default.arg is True

    def test_nickname_default_is_none(self):
        """No explicit default → SQLAlchemy treats it as NULL on
        INSERT. Pin so a refactor to `default=""` doesn't break the
        `if price.nickname:` guard in templates."""
        col = _column(StripePrice, "nickname")
        # `default=None` in mapped_column means no ColumnDefault attached.
        assert col.default is None

    def test_recurring_interval_default_is_none(self):
        """Same rationale as `nickname` — one-shot prices stay NULL."""
        col = _column(StripePrice, "recurring_interval")
        assert col.default is None

    def test_metadata_json_default_factory_is_dict(self):
        """The default MUST be `dict` (the callable, producing `{}`),
        NOT `None`. Templates do `price.metadata_json.get(...)`; a
        `None` default would crash the pricing page with
        `AttributeError: 'NoneType' object has no attribute 'get'`."""
        col = _column(StripePrice, "metadata_json")
        assert col.default is not None
        assert col.default.is_callable
        # `arg` is the wrapped callable; calling it must yield {}.
        # We don't compare identity (`is dict`) — SQLAlchemy may wrap
        # it — but the produced value is what downstream code sees.
        produced = col.default.arg({})  # SQLA passes a ctx; dict ignores it
        assert produced == {}
        assert isinstance(produced, dict)

    def test_synced_at_default_factory_is_utcnow(self):
        """The default MUST be `utcnow` (callable, produces an
        aware `datetime`). `reconciliation.py` uses this to detect
        stale mirrors; if it stays NULL on insert, the NOT NULL
        constraint fires and every webnook insert crashes."""
        col = _column(StripePrice, "synced_at")
        assert col.default is not None
        assert col.default.is_callable
        # The wrapped callable's __name__ should still be utcnow —
        # we don't compare identity because SQLAlchemy wraps it in
        # a `CallableColumnDefault`.
        assert col.default.arg.__name__ == utcnow.__name__


class TestRepr:
    """The `__repr__` is read in log lines and the debug toolbar when
    triaging Stripe issues. Pin its shape — a regression that drops the
    id or amount would make grep-by-price-id useless during a finance
    incident."""

    def test_repr_format_with_standin(self):
        """Build a duck-typed stand-in (no DB, no session) — clearer
        than a magic stub and exercises the exact code path."""

        class _StandIn:
            id = "price_1AbcXYZ"
            unit_amount_cents = 1999
            currency = "eur"
            active = True

        rendered = StripePrice.__repr__(_StandIn())  # type: ignore[arg-type]
        assert rendered == "<StripePrice price_1AbcXYZ 1999eur active=True>"

    def test_repr_starts_and_ends_correctly(self):
        """Pin the angle-bracket wrapping — Python convention for
        `__repr__` and what the debug toolbar relies on to render
        objects compactly."""

        class _StandIn:
            id = "price_x"
            unit_amount_cents = 0
            currency = "usd"
            active = False

        rendered = StripePrice.__repr__(_StandIn())  # type: ignore[arg-type]
        assert rendered.startswith("<StripePrice ")
        assert rendered.endswith(">")

    @pytest.mark.parametrize(
        ("amount", "currency", "active"),
        [
            (0, "eur", False),
            (1, "usd", True),
            (999_999, "gbp", True),
        ],
    )
    def test_repr_contains_all_diagnostic_fields(self, amount, currency, active):
        """Every diagnostic field must appear — that's what makes the
        repr useful in a log line. Parametrize across realistic
        amount / currency / active combinations."""

        class _StandIn:
            pass

        stand_in = _StandIn()
        stand_in.id = "price_diag"
        stand_in.unit_amount_cents = amount
        stand_in.currency = currency
        stand_in.active = active

        rendered = StripePrice.__repr__(stand_in)  # type: ignore[arg-type]
        assert "price_diag" in rendered
        assert f"{amount}{currency}" in rendered
        assert f"active={active}" in rendered


class TestConstructionDuckTyped:
    """The class accepts `**kwargs` for every mapped column (standard
    SQLAlchemy declarative behaviour). Pin this so a stray
    `__init__` override sneaking in is caught — `webhook.py` calls
    `StripePrice(id=…, product_id=…, …)` directly."""

    def test_construction_with_all_fields(self):
        """Mirror the kwargs the webhook handler passes — if a future
        refactor breaks kwarg construction (e.g. forces a positional
        arg), the webhook ingestion would crash on every `price.*`
        event."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        price = StripePrice(
            id="price_1AbcXYZ",
            product_id="prod_ABC",
            unit_amount_cents=1999,
            currency="eur",
            active=True,
            tax_behavior="inclusive",
            nickname="Monthly",
            recurring_interval="month",
            metadata_json={"plan": "pro"},
            synced_at=now,
        )
        assert price.id == "price_1AbcXYZ"
        assert price.product_id == "prod_ABC"
        assert price.unit_amount_cents == 1999
        assert price.currency == "eur"
        assert price.active is True
        assert price.tax_behavior == "inclusive"
        assert price.nickname == "Monthly"
        assert price.recurring_interval == "month"
        assert price.metadata_json == {"plan": "pro"}
        assert price.synced_at == now

    def test_construction_with_only_required_fields(self):
        """Optional columns (`nickname`, `recurring_interval`) MUST be
        omissible at the Python level — the webhook only sets them
        when Stripe sends them. Defaults for `active` / `metadata_json`
        / `synced_at` fire at INSERT time (not at `__init__`), so we
        don't assert their values here — that's a `b_integration`
        concern."""
        price = StripePrice(
            id="price_minimal",
            product_id="prod_M",
            unit_amount_cents=500,
            currency="eur",
            tax_behavior="unspecified",
        )
        assert price.id == "price_minimal"
        # Omitted optional attrs are simply unset on the instance —
        # they read back as None via the mapped attribute.
        assert price.nickname is None
        assert price.recurring_interval is None
