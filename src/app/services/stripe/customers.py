# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mirror the Stripe Customer billing identity into the local Organisation.

Stripe Checkout collects the VAT number + billing address (finances-02 §C) ;
this module pulls those fields back onto `Organisation.billing_*`, where the
app reads them (read-only). Pure extraction (`extract_customer_billing`) is
unit-testable ; the apply step mutates the ORM object.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from app.models.organisation import Organisation


class CustomerBilling(NamedTuple):
    """Billing fields read from a Stripe Customer. A field is `None` when
    absent from the source object — so a partial payload (e.g. a
    `customer.updated` event without expanded `tax_ids`) never wipes a
    value already mirrored."""

    email: str | None
    vat_number: str | None
    address_line1: str | None
    address_line2: str | None
    postal_code: str | None
    city: str | None
    country: str | None


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read `key` from a Stripe object — dict-like (payloads, stubs) or
    attribute access (SDK objects)."""
    if obj is None:
        return default
    if hasattr(obj, "get"):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _first_tax_id(tax_ids: Any) -> str | None:
    """Read the first VAT number from a Stripe `tax_ids` list resource.

    `tax_ids` is only present when expanded (`expand=["tax_ids"]`), so this
    returns `None` for the common unexpanded case.
    """
    data = _get(tax_ids, "data")
    if not data:
        return None
    return _get(data[0], "value")


def extract_customer_billing(customer: Any) -> CustomerBilling:
    """Pure extraction of billing fields from a Stripe Customer object."""
    address = _get(customer, "address")
    return CustomerBilling(
        email=_get(customer, "email"),
        vat_number=_first_tax_id(_get(customer, "tax_ids")),
        address_line1=_get(address, "line1"),
        address_line2=_get(address, "line2"),
        postal_code=_get(address, "postal_code"),
        city=_get(address, "city"),
        country=_get(address, "country"),
    )


def apply_customer_billing_to_org(org: Organisation, billing: CustomerBilling) -> None:
    """Write the present (non-None) billing fields onto the Organisation.

    Absent fields are left untouched, so partial payloads don't erase data.
    """
    if billing.email is not None:
        org.billing_email = billing.email
    if billing.vat_number is not None:
        org.billing_vat_number = billing.vat_number
    if billing.address_line1 is not None:
        org.billing_address_line1 = billing.address_line1
    if billing.address_line2 is not None:
        org.billing_address_line2 = billing.address_line2
    if billing.postal_code is not None:
        org.billing_postal_code = billing.postal_code
    if billing.city is not None:
        org.billing_city = billing.city
    if billing.country is not None:
        org.billing_country = billing.country


def mirror_customer_to_org(org: Organisation, customer: Any) -> None:
    """Extract billing fields from a Stripe Customer and mirror them onto
    the Organisation. Caller commits."""
    apply_customer_billing_to_org(org, extract_customer_billing(customer))
