# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP billing views."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest

from app.services.invoicing import Invoice, InvoiceLine

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User
    from app.models.organisation import Organisation


@pytest.fixture
def test_invoice(db_session: Session, test_user: User) -> Invoice:
    """Create a test invoice."""
    invoice = Invoice(
        invoice_number="INV-2024-001",
        invoice_date=arrow.get("2024-01-15"),
        owner_id=test_user.id,
        total=10000,  # 100.00 EUR in cents
    )
    db_session.add(invoice)
    db_session.flush()

    # Add invoice line
    line = InvoiceLine(
        invoice_id=invoice.id,
        description="Test service",
        quantity=1,
        unit_price=10000,
        total=10000,
    )
    db_session.add(line)
    db_session.commit()
    return invoice


@pytest.fixture
def other_user(db_session: Session, test_org: Organisation) -> User:
    """Create another user for authorization tests."""
    from app.models.auth import User

    user = User(
        email="other-user@example.com",
        first_name="Other",
        last_name="User",
        active=True,
    )
    user.organisation = test_org
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def other_user_invoice(db_session: Session, other_user: User) -> Invoice:
    """Create an invoice owned by another user."""
    invoice = Invoice(
        invoice_number="INV-2024-002",
        invoice_date=arrow.get("2024-02-15"),
        owner_id=other_user.id,
        total=20000,
    )
    db_session.add(invoice)
    db_session.commit()
    return invoice


class TestBillingPage:
    """Tests for the billing list page."""

    def test_billing_page_loads(self, logged_in_client: FlaskClient, test_user: User):
        """Test that billing page loads successfully."""
        response = logged_in_client.get("/wip/billing")
        assert response.status_code == 200

    def test_billing_page_shows_invoices(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_invoice: Invoice,
    ):
        """Test that billing page shows user's invoices."""
        response = logged_in_client.get("/wip/billing")
        assert response.status_code == 200
        html = response.data.decode()
        assert "INV-2024-001" in html

    def test_billing_page_empty_when_no_invoices(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test billing page renders with no invoices."""
        response = logged_in_client.get("/wip/billing")
        assert response.status_code == 200

    def test_billing_page_does_not_show_other_user_invoices(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        other_user_invoice: Invoice,
    ):
        """Test that billing page only shows current user's invoices."""
        response = logged_in_client.get("/wip/billing")
        assert response.status_code == 200
        html = response.data.decode()
        # Should not show other user's invoice
        assert "INV-2024-002" not in html


class TestBillingPdfDownload:
    """Tests for PDF invoice download."""

    def test_download_pdf_success(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_invoice: Invoice,
    ):
        """Test downloading PDF for own invoice."""
        with patch("app.modules.wip.views.billing.to_pdf") as mock_to_pdf:
            mock_to_pdf.return_value = b"%PDF-1.4 test content"

            response = logged_in_client.get(
                f"/wip/billing/get_pdf?invoice_id={test_invoice.id}"
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/pdf"
            assert "attachment" in response.headers["content-disposition"]
            assert "INV-2024-001.pdf" in response.headers["content-disposition"]

    def test_download_pdf_not_found(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
    ):
        """Test downloading PDF for non-existent invoice returns 404."""
        response = logged_in_client.get("/wip/billing/get_pdf?invoice_id=99999")
        assert response.status_code == 404

    def test_download_pdf_unauthorized(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        other_user_invoice: Invoice,
    ):
        """Test downloading PDF for other user's invoice is denied."""
        response = logged_in_client.get(
            f"/wip/billing/get_pdf?invoice_id={other_user_invoice.id}"
        )
        # Flask-Security redirects unauthorized requests
        assert response.status_code in (401, 302, 403)


class TestBillingCsvDownload:
    """Tests for CSV invoice download."""

    def test_download_csv_success(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_invoice: Invoice,
    ):
        """Test downloading CSV for own invoice."""
        response = logged_in_client.get(
            f"/wip/billing/get_csv?invoice_id={test_invoice.id}"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"
        assert "attachment" in response.headers["content-disposition"]
        assert "INV-2024-001.csv" in response.headers["content-disposition"]

        # Check CSV content
        csv_content = response.data.decode()
        assert "description" in csv_content
        assert "Test service" in csv_content

    def test_download_csv_not_found(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
    ):
        """Test downloading CSV for non-existent invoice returns 404."""
        response = logged_in_client.get("/wip/billing/get_csv?invoice_id=99999")
        assert response.status_code == 404

    def test_download_csv_unauthorized(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        other_user_invoice: Invoice,
    ):
        """Test downloading CSV for other user's invoice is denied."""
        response = logged_in_client.get(
            f"/wip/billing/get_csv?invoice_id={other_user_invoice.id}"
        )
        # Flask-Security redirects unauthorized requests
        assert response.status_code in (401, 302, 403)


class TestInvoiceModel:
    """Tests for Invoice model methods."""

    def test_invoice_to_csv(self, test_invoice: Invoice):
        """Test Invoice.to_csv() generates valid CSV."""
        csv_content = test_invoice.to_csv()

        # Check header
        assert "description" in csv_content
        assert "quantity" in csv_content
        assert "unit_price" in csv_content
        assert "total" in csv_content

        # Check data row
        assert "Test service" in csv_content
        assert "1" in csv_content  # quantity
        assert "100.0" in csv_content  # unit_price in EUR (10000 cents / 100)
