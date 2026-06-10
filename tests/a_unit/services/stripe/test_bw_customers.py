# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure unit tests for count_pr_bw_customers() — no DB required."""

from __future__ import annotations

from app.services.stripe.bw_customers import count_pr_bw_customers


class TestCountPrBwCustomers:
    """Test suite for count_pr_bw_customers (pure cases)."""

    def test_invalid_bw_id_returns_zero(self) -> None:
        """Non-UUID string."""
        assert count_pr_bw_customers("not-a-uuid") == 0
