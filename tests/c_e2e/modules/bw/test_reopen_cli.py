# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`flask bw reopen` reopens the BWs closed with their Stripe subscription.

Stripe cancels test-mode subscriptions after 90 days, and the webhook
closes their BW (bug #0406).
"""

from __future__ import annotations

from click.testing import CliRunner

from app.enums import BWRoleType, BWStatus, BWType
from app.flask.cli.bw import reopen
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.bw_cancellation import close_business_wall_locally
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    RoleAssignment,
    Subscription,
    SubscriptionStatus,
)


def _make_bw(session, org: Organisation, email: str) -> BusinessWall:
    owner = User(email=email, active=True)
    session.add(owner)
    session.flush()
    bw = BusinessWall(
        name=f"BW {email}",
        bw_type=BWType.PR.value,
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    session.add(bw)
    session.flush()
    session.add(
        Subscription(
            business_wall_id=bw.id,
            pricing_field="client_count",
            pricing_tier="1",
            monthly_price=8,
            annual_price=96,
            status=SubscriptionStatus.ACTIVE.value,
            stripe_subscription_id=f"sub_{email}",
        )
    )
    org.bw_id = bw.id
    session.commit()
    return bw


def _make_org(session, name: str) -> Organisation:
    org = Organisation(name=name)
    session.add(org)
    session.flush()
    return org


def test_reopens_a_bw_closed_with_its_subscription(fresh_db, app):
    session = fresh_db.session
    org = _make_org(session, "Fake-Les Propulseurs RP")
    bw = _make_bw(session, org, "marc@pr.example")
    close_business_wall_locally(bw)

    listing = CliRunner().invoke(reopen, [])
    assert f"would reopen {bw.id}" in listing.output
    session.refresh(bw)
    assert bw.status == BWStatus.SUSPENDED.value

    result = CliRunner().invoke(reopen, ["--apply"])

    assert result.exit_code == 0, result.output
    assert "1 BW(s) reopened" in result.output
    session.refresh(bw)
    session.refresh(org)
    assert bw.status == BWStatus.ACTIVE.value
    assert bw.subscription.status == SubscriptionStatus.ACTIVE.value
    assert org.bw_id == bw.id
    assert (
        session.query(RoleAssignment)
        .filter_by(business_wall_id=bw.id, role_type=BWRoleType.BW_OWNER.value)
        .one()
    )


def test_keeps_closed_a_bw_whose_organisation_has_another(fresh_db, app):
    session = fresh_db.session
    org = _make_org(session, "Fake-Tisseran RP")
    old_bw = _make_bw(session, org, "old@pr.example")
    close_business_wall_locally(old_bw)
    new_bw = _make_bw(session, org, "new@pr.example")

    result = CliRunner().invoke(reopen, ["--apply"])

    assert "0 BW(s) reopened" in result.output
    session.refresh(old_bw)
    session.refresh(org)
    assert old_bw.status == BWStatus.SUSPENDED.value
    assert org.bw_id == new_bw.id
