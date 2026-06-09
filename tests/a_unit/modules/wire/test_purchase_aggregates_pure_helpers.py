# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure-helper tests for `wire.services.purchase_aggregates`.

The three helpers under test are pure SQLAlchemy expression builders.
They take a ``post_id_predicate`` callable (or a bare column) and
return an ORM construct *without ever touching the database* :

- ``_direct_consultation_count_stmt(predicate)`` → ``Select``
  counting PAID CONSULTATION purchases grouped by ``post_id``.
- ``_gift_consultation_count_stmt(predicate)`` → ``Select`` counting
  PAID CONSULTATION_GIFT beneficiaries grouped by ``post_id``.
- ``paid_consultation_count_subquery(post_id_col)`` → a scalar
  ``ColumnElement`` summing the two correlated subqueries (used in
  ``ORDER BY`` for the « Trier > Popularité » sort).

Because these are pure functions of their inputs, the tests are
mock-free : we feed them real lambdas / columns and inspect the
returned SQLAlchemy object (type + compiled SQL string). No DB
session and no patching of any kind.

The aggregate-total helpers in the same module
(``get_user_purchase_total``, ``get_org_purchase_total``,
``list_sales_per_media`` …) genuinely orchestrate
``db.session.scalar(...)`` calls over real rows ; they belong at the
``b_integration`` tier and are intentionally NOT covered here.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Select
from sqlalchemy.sql.elements import ColumnElement

from app.modules.wire.models import ArticlePurchase
from app.modules.wire.services.purchase_aggregates import (
    _direct_consultation_count_stmt,
    _gift_consultation_count_stmt,
    paid_consultation_count_subquery,
)


def _compile(stmt: Any) -> str:
    """Render `stmt` to a literal-bound SQL string for substring asserts.

    We use ``literal_binds=True`` so parameters appear inline ; this
    makes the assertions read like English rather than chasing
    ``%(post_id_1)s`` placeholders.
    """
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def _eq_predicate(value: int) -> Callable[[Any], Any]:
    """Singular-call predicate : ``col == value`` (per-post helper)."""
    return lambda col: col == value


def _in_predicate(values: list[int]) -> Callable[[Any], Any]:
    """Batched-call predicate : ``col.in_(values)`` (wall / sort)."""
    return lambda col: col.in_(values)


class TestDirectConsultationCountStmt:
    """`_direct_consultation_count_stmt` builds the CONSULTATION
    counter — direct paid reads, grouped by ``post_id``."""

    def test_returns_a_select_statement(self):
        stmt = _direct_consultation_count_stmt(_eq_predicate(1))
        assert isinstance(stmt, Select)

    def test_predicate_receives_article_purchase_post_id_column(self):
        """The helper must hand the caller the canonical column ; that
        is the whole point of factoring the predicate out — without it
        the singular / batched callers couldn't reuse the same body."""
        captured: list[Any] = []

        def predicate(col: Any) -> Any:
            captured.append(col)
            return col == 1

        _direct_consultation_count_stmt(predicate)

        assert len(captured) == 1
        assert captured[0] is ArticlePurchase.post_id

    def test_filters_on_consultation_product_type_and_paid_status(self):
        sql = _compile(_direct_consultation_count_stmt(_eq_predicate(42)))
        # Two non-negotiable filters per ticket #0193 :
        assert "product_type = 'CONSULTATION'" in sql
        assert "status = 'PAID'" in sql
        # Reading the singular caller's intent : equality predicate.
        assert "post_id = 42" in sql

    def test_in_predicate_compiles_to_an_in_clause(self):
        """Batched caller passes ``.in_([...])`` ; the same builder
        accepts it without any branching on the SUT side."""
        sql = _compile(_direct_consultation_count_stmt(_in_predicate([7, 11, 13])))
        assert "post_id IN (7, 11, 13)" in sql

    def test_groups_by_post_id(self):
        """Result shape is ``{post_id: count}`` so the GROUP BY is
        load-bearing — the batched caller depends on it."""
        sql = _compile(_direct_consultation_count_stmt(_eq_predicate(1)))
        assert "GROUP BY wire_article_purchase.post_id" in sql

    def test_selects_post_id_and_count_alias(self):
        sql = _compile(_direct_consultation_count_stmt(_eq_predicate(1)))
        assert "SELECT wire_article_purchase.post_id" in sql
        assert "count(*) AS c" in sql

    def test_queries_the_article_purchase_table_only(self):
        """No gift table involved — direct CONSULTATION rows live on
        ``wire_article_purchase`` alone."""
        sql = _compile(_direct_consultation_count_stmt(_eq_predicate(1)))
        assert "FROM wire_article_purchase" in sql
        assert "wire_article_purchase_gift" not in sql


class TestGiftConsultationCountStmt:
    """`_gift_consultation_count_stmt` counts CONSULTATION_GIFT
    beneficiaries (one row per beneficiary, attached to the parent
    purchase) — also grouped by parent's ``post_id``."""

    def test_returns_a_select_statement(self):
        stmt = _gift_consultation_count_stmt(_eq_predicate(1))
        assert isinstance(stmt, Select)

    def test_predicate_receives_article_purchase_post_id_column(self):
        captured: list[Any] = []

        def predicate(col: Any) -> Any:
            captured.append(col)
            return col == 1

        _gift_consultation_count_stmt(predicate)

        assert len(captured) == 1
        assert captured[0] is ArticlePurchase.post_id

    def test_filters_on_consultation_gift_product_type_and_paid(self):
        sql = _compile(_gift_consultation_count_stmt(_eq_predicate(99)))
        assert "product_type = 'CONSULTATION_GIFT'" in sql
        assert "status = 'PAID'" in sql
        assert "post_id = 99" in sql

    def test_in_predicate_compiles_to_an_in_clause(self):
        sql = _compile(_gift_consultation_count_stmt(_in_predicate([3, 5])))
        assert "post_id IN (3, 5)" in sql

    def test_joins_gift_to_parent_purchase(self):
        """Each beneficiary row is anchored to the parent purchase, so
        we need the join to surface the parent's ``post_id`` and to
        gate the count by the parent's status / product_type."""
        sql = _compile(_gift_consultation_count_stmt(_eq_predicate(1)))
        assert "FROM wire_article_purchase_gift" in sql
        assert (
            "JOIN wire_article_purchase "
            "ON wire_article_purchase.id = "
            "wire_article_purchase_gift.purchase_id"
        ) in sql

    def test_counts_gift_rows_not_purchases(self):
        """Each beneficiary counts as one « vue » per ticket #0194 :
        the count is over ``ArticlePurchaseGift.id``, NOT over
        ``ArticlePurchase.id`` (a single gift purchase can span N
        beneficiaries)."""
        sql = _compile(_gift_consultation_count_stmt(_eq_predicate(1)))
        assert "count(wire_article_purchase_gift.id) AS c" in sql

    def test_groups_by_parent_post_id(self):
        sql = _compile(_gift_consultation_count_stmt(_eq_predicate(1)))
        assert "GROUP BY wire_article_purchase.post_id" in sql


class TestPaidConsultationCountSubquery:
    """`paid_consultation_count_subquery(col)` is the « vues » scalar
    expression used in ``ORDER BY`` and correlated subqueries. It must
    return a sum-of-two scalar subqueries — both correlated by
    ``col``."""

    def test_returns_a_column_element(self):
        """Used in ``ORDER BY`` / SELECT lists, so it must be a
        ``ColumnElement`` (any SQL expression of single-column type)."""
        expr = paid_consultation_count_subquery(ArticlePurchase.post_id)
        assert isinstance(expr, ColumnElement)

    def test_compiles_to_a_sum_of_two_subqueries(self):
        """The shape is exactly « direct + gifted » — that's the
        invariant the unit guarantees so display / sort / batched
        count can never diverge."""
        sql = _compile(paid_consultation_count_subquery(ArticlePurchase.post_id))
        # Top-level operator is `+` between two parenthesised SELECTs.
        assert sql.count("SELECT") == 2
        assert ") + (" in sql

    def test_direct_subquery_filters_on_consultation_paid(self):
        sql = _compile(paid_consultation_count_subquery(ArticlePurchase.post_id))
        assert "product_type = 'CONSULTATION'" in sql
        assert "status = 'PAID'" in sql

    def test_gift_subquery_joins_and_filters(self):
        sql = _compile(paid_consultation_count_subquery(ArticlePurchase.post_id))
        assert "FROM wire_article_purchase_gift" in sql
        assert "product_type = 'CONSULTATION_GIFT'" in sql

    def test_correlates_on_provided_post_id_column(self):
        """The caller's column appears verbatim in both subqueries —
        that's how the correlation hooks the outer row in."""
        expr = paid_consultation_count_subquery(ArticlePurchase.post_id)
        sql = _compile(expr)
        # The literal column is present on both sides of the `+`.
        # SQLAlchemy compiles `col == col` as
        # `wire_article_purchase.post_id = wire_article_purchase.post_id`
        # in literal-binds mode — checking for two occurrences proves
        # both subqueries reference it.
        assert sql.count("wire_article_purchase.post_id") >= 4

    @pytest.mark.parametrize(
        "predicate_factory",
        [_eq_predicate, _in_predicate],
        ids=["equality (singular)", "in_ (batched)"],
    )
    def test_helpers_share_filters_and_grouping(
        self,
        predicate_factory: Callable[..., Any],
    ) -> None:
        """Both helpers, regardless of predicate shape, must emit the
        same status filter and the same group-by clause — that's the
        contract that lets callers blindly merge their results into a
        single ``{post_id: count}`` dict."""
        if predicate_factory is _eq_predicate:
            predicate = predicate_factory(1)
        else:
            predicate = predicate_factory([1, 2])

        direct_sql = _compile(_direct_consultation_count_stmt(predicate))
        gift_sql = _compile(_gift_consultation_count_stmt(predicate))

        for sql in (direct_sql, gift_sql):
            assert "status = 'PAID'" in sql
            assert "GROUP BY wire_article_purchase.post_id" in sql
