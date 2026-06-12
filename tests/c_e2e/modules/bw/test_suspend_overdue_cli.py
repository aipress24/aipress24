# Copyright (c) 2025-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E test for `flask bw suspend-overdue` — the nightly job that suspends
BWs whose subscription has been PAST_DUE beyond the grace window
(spec `finances-02.md` §B)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from click.testing import CliRunner

from app.flask.cli.bw import suspend_overdue
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.bw.bw_activation.models.business_wall import BWType


def _make_bw_with_past_due_sub(session, *, days_overdue: int, email: str):
    owner = User(email=email, active=True)
    session.add(owner)
    session.flush()
    org = Organisation(name=f"Org {email}")
    session.add(org)
    session.flush()
    bw = BusinessWall(
        name=f"BW {email}",
        bw_type=BWType.MEDIA.value,
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    session.add(bw)
    session.flush()
    sub = Subscription(
        business_wall_id=bw.id,
        pricing_field="employee_count",
        pricing_tier="1-10",
        monthly_price=10,
        annual_price=100,
        status=SubscriptionStatus.PAST_DUE.value,
        past_due_since=datetime.now(UTC) - timedelta(days=days_overdue),
        stripe_subscription_id=f"sub_{email}",
    )
    session.add(sub)
    session.commit()
    return bw


class TestSuspendOverdueCLI:
    def test_suspends_bw_past_due_beyond_grace(self, fresh_db, app):
        bw = _make_bw_with_past_due_sub(
            fresh_db.session, days_overdue=8, email="overdue@press.example"
        )

        result = CliRunner().invoke(suspend_overdue, [])

        assert result.exit_code == 0, result.output
        fresh_db.session.refresh(bw)
        assert bw.status == BWStatus.SUSPENDED.value
        assert "1 BW(s) suspended" in result.output

    def test_keeps_bw_within_grace(self, fresh_db, app):
        bw = _make_bw_with_past_due_sub(
            fresh_db.session, days_overdue=3, email="recent@press.example"
        )

        result = CliRunner().invoke(suspend_overdue, [])

        assert result.exit_code == 0, result.output
        fresh_db.session.refresh(bw)
        assert bw.status == BWStatus.ACTIVE.value
        assert "0 BW(s) suspended" in result.output

    def test_custom_grace_days(self, fresh_db, app):
        bw = _make_bw_with_past_due_sub(
            fresh_db.session, days_overdue=3, email="custom@press.example"
        )

        # With a 2-day grace, a 3-day-overdue BW is suspended.
        result = CliRunner().invoke(suspend_overdue, ["--grace-days", "2"])

        assert result.exit_code == 0, result.output
        fresh_db.session.refresh(bw)
        assert bw.status == BWStatus.SUSPENDED.value
