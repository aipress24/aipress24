# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure unit tests for SalesLedgerExporter.cell_value — row → cell mapping
(spec `finances-02.md` §A). No DB, no app context."""

from __future__ import annotations

from datetime import UTC, datetime

import arrow
import pytest

from app.modules.admin.views._export import SalesLedgerExporter
from app.modules.wire.services.purchase_aggregates import PaidPurchaseRow


def _row(**overrides) -> PaidPurchaseRow:
    base = {
        "purchase_id": 1,
        "paid_at": arrow.get("2026-06-10T08:00:00+00:00"),
        "product_type": "consultation",
        "amount_cents": 1000,
        "currency": "EUR",
        "buyer_email": "b@example.com",
        "buyer_org_name": "ACME",
        "media_org_name": "Le Média",
        "article_id": 42,
        "article_title": "Titre",
        "stripe_payment_intent_id": "pi_1",
    }
    base.update(overrides)
    return PaidPurchaseRow(**base)


class TestSalesLedgerCellValue:
    @pytest.mark.parametrize(
        ("product", "label"),
        [
            ("consultation", "Consultation"),
            ("consultation_gift", "Consultation (cadeau)"),
            ("justificatif", "Justificatif"),
            ("cession", "Cession de droits"),
            ("unknown_x", "unknown_x"),  # unknown → passthrough, never a crash
        ],
    )
    def test_product_type_label(self, product: str, label: str):
        exporter = SalesLedgerExporter()
        cell = exporter.cell_value(_row(product_type=product), "product_type")
        assert cell == label

    def test_amount_cents_to_euro(self):
        exporter = SalesLedgerExporter()
        assert exporter.cell_value(_row(amount_cents=1234), "amount_ht_eur") == 12.34

    def test_article_id_is_string(self):
        exporter = SalesLedgerExporter()
        assert exporter.cell_value(_row(article_id=42), "article_id") == "42"

    def test_paid_at_none_is_blank(self):
        exporter = SalesLedgerExporter()
        assert exporter.cell_value(_row(paid_at=None), "paid_at") == ""

    def test_paid_at_arrow_becomes_naive_datetime(self):
        exporter = SalesLedgerExporter()
        value = exporter.cell_value(_row(), "paid_at")
        assert isinstance(value, datetime)
        assert value.tzinfo is None

    def test_passthrough_text_columns(self):
        exporter = SalesLedgerExporter()
        row = _row()
        assert exporter.cell_value(row, "currency") == "EUR"
        assert exporter.cell_value(row, "buyer_email") == "b@example.com"
        assert exporter.cell_value(row, "buyer_org_name") == "ACME"
        assert exporter.cell_value(row, "media_org_name") == "Le Média"
        assert exporter.cell_value(row, "article_title") == "Titre"
        assert exporter.cell_value(row, "stripe_payment_intent_id") == "pi_1"

    def test_unknown_column_raises(self):
        exporter = SalesLedgerExporter()
        with pytest.raises(KeyError):
            exporter.cell_value(_row(), "nope")


class TestSalesLedgerMeta:
    def test_every_column_has_a_definition(self):
        exporter = SalesLedgerExporter()
        exporter.init_columns_definition()
        for name in exporter.columns:
            assert name in exporter.columns_definition

    def test_filename_and_title(self):
        exporter = SalesLedgerExporter()
        exporter.date_now = datetime(2026, 6, 12, 9, 0, tzinfo=UTC)
        assert exporter.filename == "ventes_a_l_acte_2026-06-12.ods"
        assert "2026" in exporter.title
