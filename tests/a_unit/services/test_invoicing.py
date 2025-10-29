# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/invoicing module."""

from __future__ import annotations

import arrow
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.services.invoicing import Invoice, InvoiceLine


class TestInvoiceModel:
    """Test suite for Invoice model."""

    def test_invoice_to_csv_empty(self, db: SQLAlchemy) -> None:
        """Test to_csv with no invoice lines."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        invoice = Invoice(
            owner=user,
            invoice_number="INV-001",
            invoice_date=arrow.now(),
            total=0,
        )
        db.session.add(invoice)
        db.session.flush()

        csv_output = invoice.to_csv()

        # Should have header only
        lines = csv_output.strip().split("\n")
        assert len(lines) == 1
        assert "description" in lines[0]
        assert "quantity" in lines[0]
        assert "unit_price" in lines[0]

    def test_invoice_to_csv_single_line(self, db: SQLAlchemy) -> None:
        """Test to_csv with a single invoice line."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        invoice = Invoice(
            owner=user,
            invoice_number="INV-002",
            invoice_date=arrow.now(),
            total=10000,  # 100.00 EUR in cents
        )
        db.session.add(invoice)
        db.session.flush()

        line = InvoiceLine(
            invoice=invoice,
            description="Consulting Service",
            quantity=2,
            unit_price=5000,  # 50.00 EUR in cents
            total=10000,  # 100.00 EUR in cents
        )
        db.session.add(line)
        db.session.flush()

        csv_output = invoice.to_csv()

        lines = csv_output.strip().split("\n")
        assert len(lines) == 2  # Header + 1 data line

        # Check header
        assert "description" in lines[0]

        # Check data
        assert "Consulting Service" in lines[1]
        assert "2" in lines[1]
        assert "50.0" in lines[1]  # unit_price in EUR
        assert "100.0" in lines[1]  # total in EUR

    def test_invoice_to_csv_multiple_lines(self, db: SQLAlchemy) -> None:
        """Test to_csv with multiple invoice lines."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        invoice = Invoice(
            owner=user,
            invoice_number="INV-003",
            invoice_date=arrow.now(),
            total=17500,
        )
        db.session.add(invoice)
        db.session.flush()

        line1 = InvoiceLine(
            invoice=invoice,
            description="Web Development",
            quantity=5,
            unit_price=2000,  # 20.00 EUR
            total=10000,  # 100.00 EUR
        )
        line2 = InvoiceLine(
            invoice=invoice,
            description="Design Work",
            quantity=3,
            unit_price=2500,  # 25.00 EUR
            total=7500,  # 75.00 EUR
        )
        db.session.add_all([line1, line2])
        db.session.flush()

        csv_output = invoice.to_csv()

        lines = csv_output.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data lines

        # Check both services are present
        csv_text = csv_output
        assert "Web Development" in csv_text
        assert "Design Work" in csv_text

    def test_invoice_to_csv_price_conversion(self, db: SQLAlchemy) -> None:
        """Test that prices are correctly converted from cents to EUR."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        invoice = Invoice(
            owner=user,
            invoice_number="INV-004",
            invoice_date=arrow.now(),
            total=12345,  # 123.45 EUR
        )
        db.session.add(invoice)
        db.session.flush()

        line = InvoiceLine(
            invoice=invoice,
            description="Test Item",
            quantity=1,
            unit_price=12345,  # 123.45 EUR
            total=12345,
        )
        db.session.add(line)
        db.session.flush()

        csv_output = invoice.to_csv()

        # Prices should be divided by 100
        assert "123.45" in csv_output

    def test_invoice_line_relationship(self, db: SQLAlchemy) -> None:
        """Test relationship between Invoice and InvoiceLine."""
        user = User(email="test@example.com")
        db.session.add(user)
        db.session.flush()

        invoice = Invoice(
            owner=user,
            invoice_number="INV-005",
            invoice_date=arrow.now(),
            total=5000,
        )
        db.session.add(invoice)
        db.session.flush()

        line1 = InvoiceLine(
            invoice=invoice,
            description="Item 1",
            quantity=1,
            unit_price=3000,
            total=3000,
        )
        line2 = InvoiceLine(
            invoice=invoice,
            description="Item 2",
            quantity=1,
            unit_price=2000,
            total=2000,
        )
        db.session.add_all([line1, line2])
        db.session.flush()

        # Test invoice.lines relationship
        assert len(invoice.lines) == 2
        assert line1 in invoice.lines
        assert line2 in invoice.lines

        # Test line.invoice relationship
        assert line1.invoice == invoice
        assert line2.invoice == invoice
