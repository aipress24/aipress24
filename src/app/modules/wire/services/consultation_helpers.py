# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared helpers for consultation access duration checks."""

from __future__ import annotations

import arrow
import sqlalchemy as sa

from app.modules.wire.models import ArticlePurchase
from app.settings.constants import ARTICLE_CONSULTATION_DURATION


def consultation_access_cutoff() -> arrow.Arrow:
    """Return the earliest valid purchase date for consultation access.

    A consultation right expires after "ARTICLE_CONSULTATION_DURATION"
    days.
    """
    return arrow.utcnow().shift(days=-ARTICLE_CONSULTATION_DURATION)


def purchase_within_duration_clause(column) -> sa.ColumnElement[bool]:
    """SQL expression: `column` (paid_at/timestamp) is within the
    consultation duration window."""
    return (
        sa.func.coalesce(column, ArticlePurchase.timestamp)
        >= consultation_access_cutoff()
    )
