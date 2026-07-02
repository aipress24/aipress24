# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the admin Stripe-products view model."""

from __future__ import annotations

from stripe import Product

from app.modules.admin.views.stripe_products import ProductView


def _make_view() -> ProductView:
    product = Product.construct_from(
        {"id": "prod_1", "name": "Test", "tax_code": "txcd_1"}, key=None
    )
    return ProductView(
        product=product,
        created_fmt="01/01/2026 00:00",
        updated_fmt="02/01/2026 00:00",
        tax_sim={"amount_tax": 20.0, "breakdown": "TVA (20%)"},
        tax_code_name="General",
    )


def test_computed_fields_return_own_values():
    """The presentation fields are read straight off the wrapper, not
    the wrapped product."""
    view = _make_view()
    assert view.created_fmt == "01/01/2026 00:00"
    assert view.updated_fmt == "02/01/2026 00:00"
    assert view.tax_code_name == "General"
    assert view.tax_sim == {"amount_tax": 20.0, "breakdown": "TVA (20%)"}


def test_native_attributes_delegate_to_product():
    """Unknown attributes fall through to the wrapped Stripe Product, so
    the template reads native fields without us monkey-patching the
    typed model."""
    view = _make_view()
    assert view.name == "Test"
    assert view.id == "prod_1"
    assert view.tax_code == "txcd_1"
