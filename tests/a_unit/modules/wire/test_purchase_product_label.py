# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""One label per purchase product, shared by every sales and purchases
screen and export (#0364: a gifted consultation showed its raw code)."""

from __future__ import annotations

import pytest

from app.modules.wire.models import PurchaseProduct, purchase_product_label


@pytest.mark.parametrize("product", list(PurchaseProduct))
def test_every_product_has_a_label(product: PurchaseProduct) -> None:
    assert purchase_product_label(product) != product.value


def test_accepts_the_raw_code() -> None:
    assert purchase_product_label("consultation_gift") == "Consultation offerte"


def test_unknown_code_is_passed_through() -> None:
    assert purchase_product_label("unknown_x") == "unknown_x"
