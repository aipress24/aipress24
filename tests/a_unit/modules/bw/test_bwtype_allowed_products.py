# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `BWTYPE_ALLOWED_PRODUCTS` in
`app.modules.bw.bw_activation.config`.

This dict maps each BWType to the list of Stripe product codes that
will activate it. It's consumed by `_get_bw_type_from_product` (in
`stripe/views/webhook.py`) to decide which BW tier a paying customer
gets after a successful Checkout.

The contract this test pins :
- every BWType paid tier has at least one product code
- product codes follow the BW4*-* convention so a typo in either
  side surfaces immediately
- no product code appears under two BWTypes (would silently
  upgrade/downgrade buyers depending on lookup order)
"""

from __future__ import annotations

from app.modules.bw.bw_activation.bw_invitation import (
    _FAILURE_MESSAGES,
    InvitationOutcomeCode,
)
from app.modules.bw.bw_activation.config import BWTYPE_ALLOWED_PRODUCTS
from app.modules.bw.bw_activation.models import BWType


class TestBwtypeAllowedProducts:
    def test_all_bw_types_present(self):
        """The dict carries every BW type (paid and free). Free tiers
        now go through Stripe checkout with a 0 EUR price, so they need
        an allowed product mapping too."""
        keys = set(BWTYPE_ALLOWED_PRODUCTS.keys())
        for member in BWType:
            assert member.value in keys, (
                f"BWType {member.value!r} is missing from BWTYPE_ALLOWED_PRODUCTS"
            )

    def test_every_entry_is_a_non_empty_list(self):
        """Each BWType must have at least one product code, otherwise
        no Stripe purchase can ever activate that tier."""
        for bw_type, products in BWTYPE_ALLOWED_PRODUCTS.items():
            assert isinstance(products, list), (
                f"BWTYPE_ALLOWED_PRODUCTS[{bw_type!r}] must be a list"
            )
            assert products, (
                f"BWTYPE_ALLOWED_PRODUCTS[{bw_type!r}] is empty — no "
                "Stripe purchase can activate this BW type"
            )

    def test_product_codes_use_bw4_prefix(self):
        """All product codes follow the `BW4*` convention. Pin so a
        typo (`BW3T-...` or `bw4t-...`) gets caught at PR time."""
        for products in BWTYPE_ALLOWED_PRODUCTS.values():
            for code in products:
                assert code.startswith("BW4"), (
                    f"Product code {code!r} should start with `BW4` ; "
                    "see config.py docs."
                )

    def test_product_codes_are_unique_or_explicitly_aliased(self):
        """No product code may belong to two BWTypes, except for the
        intentional micro→media alias (BW4Micro no longer exists in
        Stripe, so micro reuses the media product). Cross-type leakage
        would otherwise make the Stripe-checkout-to-BW lookup
        non-deterministic (depends on iteration order of the dict)."""
        allowed_aliases = {("media", "micro")}
        seen: dict[str, str] = {}
        for bw_type, products in BWTYPE_ALLOWED_PRODUCTS.items():
            for code in products:
                if code in seen:
                    pair = tuple(sorted([seen[code], bw_type]))
                    assert pair in allowed_aliases, (
                        f"product {code!r} appears under both "
                        f"BWType {seen[code]!r} and {bw_type!r}"
                    )
                else:
                    seen[code] = bw_type

    def test_pr_has_single_product(self):
        """PR (PR Agency) is a single-product tier — only `BW4PR`
        activates it. Pin so a future size-bracketed PR offering
        is a conscious choice, not an accidental addition."""
        pr_products = BWTYPE_ALLOWED_PRODUCTS[BWType.PR.value]
        assert pr_products == ["BW4PR"]

    def test_transformers_covers_all_size_brackets(self):
        """Transformers (« BW4T ») is offered at Solo / TPE / PME /
        ETI / GE size brackets — pin the 5-size lineup so a missing
        size doesn't ship to prod with a broken Stripe lookup."""
        transformers = set(BWTYPE_ALLOWED_PRODUCTS[BWType.TRANSFORMERS.value])
        for size in ("Solo", "TPE", "PME", "ETI", "GE"):
            assert f"BW4T-{size}" in transformers, (
                f"BW4T-{size} missing from BWTYPE_ALLOWED_PRODUCTS"
            )

    def test_leaders_experts_covers_all_size_brackets(self):
        """Leaders & Experts (« BW4L&E ») mirrors Transformers' 5
        size brackets. Pin so a refactor that drops one tier silently
        breaks paying customers."""
        leaders = set(BWTYPE_ALLOWED_PRODUCTS[BWType.LEADERS_EXPERTS.value])
        for size in ("Solo", "TPE", "PME", "ETI", "GE"):
            assert f"BW4L&E-{size}" in leaders, (
                f"BW4L&E-{size} missing from BWTYPE_ALLOWED_PRODUCTS"
            )

    def test_size_codes_match_taille_orga_ontology(self):
        """The size suffixes (TPE/PME/ETI/GE) match the
        `taille_organisation` KYC ontology codes Erick already pinned
        in `taille_orga_for_employee_count` (Solo is a separate
        marker). Pin so a future ontology rename gets caught here."""
        all_sizes = set()
        for products in BWTYPE_ALLOWED_PRODUCTS.values():
            for code in products:
                # Strip the BW4*- prefix to get the size suffix.
                if "-" in code:
                    all_sizes.add(code.rsplit("-", 1)[-1])

        # Pin the canonical set : the four taille_organisation codes
        # plus the « Solo » marker.
        assert all_sizes == {"Solo", "TPE", "PME", "ETI", "GE"}


class TestFailureMessagesCompleteness:
    """Pin that every `InvitationOutcomeCode.FAILED_*` has an
    `admin_message` mapped in `_FAILURE_MESSAGES`. A missing entry
    here would render as an empty flash banner — the admin sees
    « something went wrong » without any explanation."""

    def test_every_failure_code_has_a_message(self):
        failure_codes = {
            c for c in InvitationOutcomeCode if c.value.startswith("failed_")
        }
        missing = [c.value for c in failure_codes if c.value not in _FAILURE_MESSAGES]
        assert not missing, f"FAILED_* codes without _FAILURE_MESSAGES entry: {missing}"

    def test_no_message_for_success_codes(self):
        """Conversely : success / idempotent codes must NOT have a
        message (the admin doesn't get a flash for an invite that
        worked). Pin so a future « show every outcome » regression
        doesn't accidentally spam the admin with success banners."""
        for code in InvitationOutcomeCode:
            if not code.value.startswith("failed_"):
                assert code.value not in _FAILURE_MESSAGES, (
                    f"Non-FAILED code {code.value!r} has an "
                    "admin_message — would spam the admin's flash."
                )

    def test_messages_are_non_empty_french_strings(self):
        """Every message is a meaningful French sentence (the UI
        language). Pin so a future placeholder leaking into prod
        (`"TODO"` etc.) gets caught."""
        for code, message in _FAILURE_MESSAGES.items():
            assert isinstance(message, str)
            assert len(message) > 10, (
                f"Message for {code!r} suspiciously short: {message!r}"
            )
