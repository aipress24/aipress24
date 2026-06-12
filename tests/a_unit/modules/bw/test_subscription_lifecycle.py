# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure unit tests for the subscription-lifecycle transitions
(spec `finances-02.md` §B). No DB, no app context."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.bw.bw_activation.models import BWStatus, SubscriptionStatus
from app.modules.bw.bw_activation.subscription_lifecycle import (
    SUBSCRIPTION_GRACE_DAYS,
    clear_past_due,
    is_overdue,
    is_recovery_needed,
    mark_past_due,
)

NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)


class TestMarkPastDue:
    def test_first_failure_stamps_now(self):
        status, since = mark_past_due(SubscriptionStatus.ACTIVE.value, None, NOW)
        assert status == SubscriptionStatus.PAST_DUE.value
        assert since == NOW

    def test_replay_keeps_original_since(self):
        """Idempotent: a second failure must not move the grace clock."""
        first = NOW - timedelta(days=3)
        status, since = mark_past_due(SubscriptionStatus.PAST_DUE.value, first, NOW)
        assert status == SubscriptionStatus.PAST_DUE.value
        assert since == first


class TestClearPastDue:
    def test_suspended_bw_is_reactivated(self):
        sub_status, bw_status = clear_past_due(
            SubscriptionStatus.PAST_DUE.value, BWStatus.SUSPENDED.value
        )
        assert sub_status == SubscriptionStatus.ACTIVE.value
        assert bw_status == BWStatus.ACTIVE.value

    def test_active_bw_left_untouched(self):
        sub_status, bw_status = clear_past_due(
            SubscriptionStatus.PAST_DUE.value, BWStatus.ACTIVE.value
        )
        assert sub_status == SubscriptionStatus.ACTIVE.value
        assert bw_status == BWStatus.ACTIVE.value

    def test_cancelled_bw_does_not_revive(self):
        """A payment on a CANCELLED BW must not silently bring it back."""
        _, bw_status = clear_past_due(
            SubscriptionStatus.PAST_DUE.value, BWStatus.CANCELLED.value
        )
        assert bw_status == BWStatus.CANCELLED.value


class TestIsRecoveryNeeded:
    def test_normal_renewal_needs_nothing(self):
        assert is_recovery_needed(SubscriptionStatus.ACTIVE.value, None) is False

    def test_past_due_needs_recovery(self):
        assert is_recovery_needed(SubscriptionStatus.PAST_DUE.value, NOW) is True

    def test_active_but_stamped_needs_recovery(self):
        assert is_recovery_needed(SubscriptionStatus.ACTIVE.value, NOW) is True


class TestIsOverdue:
    def test_within_grace_is_not_overdue(self):
        since = NOW - timedelta(days=SUBSCRIPTION_GRACE_DAYS - 1)
        assert is_overdue(SubscriptionStatus.PAST_DUE.value, since, NOW) is False

    def test_beyond_grace_is_overdue(self):
        since = NOW - timedelta(days=SUBSCRIPTION_GRACE_DAYS + 1)
        assert is_overdue(SubscriptionStatus.PAST_DUE.value, since, NOW) is True

    def test_exactly_at_grace_boundary_is_overdue(self):
        since = NOW - timedelta(days=SUBSCRIPTION_GRACE_DAYS)
        assert is_overdue(SubscriptionStatus.PAST_DUE.value, since, NOW) is True

    def test_active_subscription_never_overdue(self):
        since = NOW - timedelta(days=365)
        assert is_overdue(SubscriptionStatus.ACTIVE.value, since, NOW) is False

    def test_past_due_without_since_is_not_overdue(self):
        assert is_overdue(SubscriptionStatus.PAST_DUE.value, None, NOW) is False
