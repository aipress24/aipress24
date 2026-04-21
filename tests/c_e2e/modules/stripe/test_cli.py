# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""CLI tests for `flask stripe` commands."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from app.flask.cli.stripe import reconcile, simulate_checkout
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Subscription,
)


def _mk_bw_draft(session) -> BusinessWall:
    owner = User(
        email=f"o-{uuid.uuid4().hex[:6]}@example.com",
        first_name="O",
        last_name="T",
        active=True,
    )
    session.add(owner)
    session.flush()
    org = Organisation(name=f"Org-{uuid.uuid4().hex[:6]}")
    session.add(org)
    session.flush()
    owner.organisation_id = org.id

    bw = BusinessWall(
        bw_type="pr",
        status=BWStatus.DRAFT.value,
        is_free=False,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    session.add(bw)
    session.flush()
    org.bw_id = bw.id
    session.commit()
    return bw


class TestSimulateCheckoutCLI:
    def test_activates_bw_via_fake_event(self, fresh_db, app):
        bw = _mk_bw_draft(fresh_db.session)

        runner = CliRunner()
        result = runner.invoke(
            simulate_checkout,
            [str(bw.id), "--customer-id", "cus_x", "--subscription-id", "sub_x"],
        )

        assert result.exit_code == 0, result.output
        fresh_db.session.refresh(bw)
        assert bw.status == BWStatus.ACTIVE.value
        sub = (
            fresh_db.session.query(Subscription)
            .filter(Subscription.business_wall_id == bw.id)
            .one()
        )
        assert sub.stripe_customer_id == "cus_x"
        assert sub.stripe_subscription_id == "sub_x"

    def test_rejects_invalid_uuid(self, fresh_db, app):
        runner = CliRunner()
        result = runner.invoke(simulate_checkout, ["not-a-uuid"])
        assert result.exit_code == 1
        assert "Invalid BW UUID" in result.output


class TestReconcileCLI:
    def test_no_drift_exits_zero(self, fresh_db, app):
        runner = CliRunner()
        with patch(
            "app.services.stripe.reconciliation.load_stripe_api_key",
            return_value=True,
        ):
            result = runner.invoke(reconcile, [])
        assert result.exit_code == 0
        assert "No drift" in result.output

    def test_drift_exits_nonzero(self, fresh_db, app):
        session = fresh_db.session
        bw = _mk_bw_draft(session)
        session.add(
            Subscription(
                business_wall_id=bw.id,
                status="active",
                pricing_field="stripe",
                pricing_tier="via_pricing_table",
                monthly_price=0,
                annual_price=0,
                stripe_subscription_id="sub_drifted",
                stripe_customer_id="cus_x",
            )
        )
        session.commit()

        runner = CliRunner()
        with patch(
            "app.services.stripe.reconciliation.load_stripe_api_key",
            return_value=True,
        ), patch(
            "stripe.Subscription.retrieve",
            return_value=SimpleNamespace(status="canceled"),
        ):
            result = runner.invoke(reconcile, [])

        assert result.exit_code == 1
        assert "drift" in result.output.lower()
