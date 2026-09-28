# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""#0364 — the publisher's part of a sale, computed on whole cents."""

from __future__ import annotations

import pytest

from app.modules.wip.views.ventes import publisher_share_cents
from app.settings.constants import PUBLISHER_REVENUE_SHARE_PERCENT


@pytest.mark.parametrize(
    ("amount_cents", "share_cents"),
    [(0, 0), (3000, 1500), (50, 25), (101, 51), (1, 1)],
)
def test_half_of_a_sale_rounded_half_up_to_the_cent(
    amount_cents: int, share_cents: int
) -> None:
    assert PUBLISHER_REVENUE_SHARE_PERCENT == 50  # the CGV split these pin

    assert publisher_share_cents(amount_cents) == share_cents
