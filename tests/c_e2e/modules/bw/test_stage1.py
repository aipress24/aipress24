# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for BW stage1 routes (subscription confirmation).

These tests verify the index, confirm_subscription, select_subscription,
activation_choice, and information routes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.enums import ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from tests.c_e2e.conftest import make_authenticated_client
from tests.c_e2e.modules.bw.conftest import create_bw_test_data

if TYPE_CHECKING:
    from flask import Flask


def _create_user_with_profile(db, org: Organisation, email_prefix: str) -> User:
    """Create a user with KYCProfile for testing."""
    user = User(
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        first_name=email_prefix.title(),
        last_name="User",
        active=True,
    )
    user.organisation = org
    user.organisation_id = org.id
    db.session.add(user)
    db.session.commit()

    profile = KYCProfile(
        user_id=user.id,
        profile_code=ProfileEnum.PM_DIR.name,
    )
    db.session.add(profile)
    db.session.commit()

    return user


# -----------------------------------------------------------------------------
# Tests: Index route
# -----------------------------------------------------------------------------


class TestIndex:
    """E2E tests for GET /BW/ (index)."""

    def test_redirects_to_dashboard_when_user_has_active_bw(self, app: Flask, fresh_db):
        """Index redirects to dashboard if user has an active BW."""
        data = create_bw_test_data(fresh_db)
        client = make_authenticated_client(app, data["media_owner"])

        response = client.get("/BW/", follow_redirects=False)

        assert response.status_code == 302
        assert "dashboard" in response.location

    def test_redirects_to_confirm_subscription_when_no_bw(self, app: Flask, fresh_db):
        """Index redirects to confirm-subscription if user has no BW."""
        # Create user with org but no BW
        org = Organisation(name="New Org")
        fresh_db.session.add(org)
        fresh_db.session.commit()

        user = _create_user_with_profile(fresh_db, org, "newuser")
        client = make_authenticated_client(app, user)

        response = client.get("/BW/", follow_redirects=False)

        assert response.status_code == 302
        assert "confirm-subscription" in response.location

    def test_no_organisation_proceeds_into_wizard(
        self, app: Flask, fresh_db
    ):
        """Index allows users without an organisation to enter the
        BW wizard (the org is auto-created downstream during
        `create_new_free_bw_record`). Bug #0117 lifted the
        previous « must have an org » gate that blocked
        single-person profiles like associations of journalists.
        """
        user = User(
            email=f"noorg_{uuid.uuid4().hex[:8]}@example.com",
            first_name="No",
            last_name="Org",
            active=True,
        )
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        response = client.get("/BW/", follow_redirects=False)

        assert response.status_code == 302
        # Org-less users now proceed to the subscription
        # confirmation step rather than the rejection page.
        assert "confirm-subscription" in response.location, (
            f"expected redirect to confirm-subscription, got "
            f"{response.location!r}"
        )

    def test_redirects_to_not_authorized_when_organisation_deleted(
        self, app: Flask, fresh_db
    ):
        """A user whose organisation is soft-deleted (e.g. a user
        whose registration was rejected) IS still blocked at the
        index gate."""
        org = Organisation(name=f"DeletedOrg_{uuid.uuid4().hex[:8]}")
        org.deleted_at = datetime.now(UTC)
        fresh_db.session.add(org)
        fresh_db.session.flush()
        user = User(
            email=f"deleted_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Del",
            last_name="Org",
            active=True,
            organisation_id=org.id,
        )
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        response = client.get("/BW/", follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not-authorized" in response.location
            or "not_authorized" in response.location
        ), f"got {response.location!r}"

    def test_redirects_non_manager_to_not_authorized(self, app: Flask, fresh_db):
        """Index redirects to not-authorized if user is not BW manager."""
        data = create_bw_test_data(fresh_db)

        # Create another user in the SAME organisation (but not owner/manager)
        non_manager = User(
            email=f"nonmgr_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Non",
            last_name="Manager",
            active=True,
        )
        non_manager.organisation = data["media_org"]
        non_manager.organisation_id = data["media_org"].id
        fresh_db.session.add(non_manager)
        fresh_db.session.commit()

        client = make_authenticated_client(app, non_manager)

        response = client.get("/BW/", follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not-authorized" in response.location
            or "not_authorized" in response.location
        )


# -----------------------------------------------------------------------------
# Tests: Confirm Subscription route
# -----------------------------------------------------------------------------


class TestConfirmSubscription:
    """E2E tests for GET /BW/confirm-subscription."""

    def test_displays_subscription_options(self, app: Flask, fresh_db):
        """Confirm subscription page displays subscription options."""
        org = Organisation(name="New Org")
        fresh_db.session.add(org)
        fresh_db.session.commit()

        user = User(
            email=f"sub_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Sub",
            last_name="User",
            active=True,
        )
        user.organisation = org
        user.organisation_id = org.id
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        response = client.get("/BW/confirm-subscription")

        assert response.status_code == 200

    def test_no_organisation_proceeds_to_subscription_page(
        self, app: Flask, fresh_db
    ):
        """Confirm-subscription renders for users without an
        organisation — bug #0117 lifted the org gate so
        single-person profiles can start the BW wizard. The org
        is auto-created later by `_create_required_organisation`.
        """
        user = User(
            email=f"nosub_{uuid.uuid4().hex[:8]}@example.com",
            first_name="No",
            last_name="Sub",
            active=True,
        )
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        response = client.get(
            "/BW/confirm-subscription", follow_redirects=False
        )

        assert response.status_code == 200, (
            f"expected the subscription page to render (200), got "
            f"{response.status_code}"
        )


# -----------------------------------------------------------------------------
# Tests: Select Subscription route
# -----------------------------------------------------------------------------


class TestSelectSubscription:
    """E2E tests for POST /BW/select-subscription/<bw_type>."""

    def test_selects_valid_subscription_type(self, app: Flask, fresh_db):
        """Selecting valid subscription type redirects to nominate_contacts."""
        org = Organisation(name="Select Org")
        fresh_db.session.add(org)
        fresh_db.session.commit()

        user = User(
            email=f"select_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Select",
            last_name="User",
            active=True,
        )
        user.organisation = org
        user.organisation_id = org.id
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        response = client.post("/BW/select-subscription/media", follow_redirects=False)

        assert response.status_code == 302
        assert "nominate-contacts" in response.location

    def test_redirects_for_invalid_subscription_type(self, app: Flask, fresh_db):
        """Invalid subscription type redirects back to confirm subscription."""
        org = Organisation(name="Invalid Org")
        fresh_db.session.add(org)
        fresh_db.session.commit()

        user = User(
            email=f"invalid_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Invalid",
            last_name="User",
            active=True,
        )
        user.organisation = org
        user.organisation_id = org.id
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        response = client.post(
            "/BW/select-subscription/invalid_type", follow_redirects=False
        )

        assert response.status_code == 302
        assert "confirm-subscription" in response.location


# -----------------------------------------------------------------------------
# Tests: Activation Choice route
# -----------------------------------------------------------------------------


class TestActivationChoice:
    """E2E tests for GET /BW/activation-choice."""

    def test_redirects_when_subscription_not_confirmed(self, app: Flask, fresh_db):
        """Activation choice redirects if subscription not confirmed."""
        org = Organisation(name="Choice Org")
        fresh_db.session.add(org)
        fresh_db.session.commit()

        user = User(
            email=f"choice_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Choice",
            last_name="User",
            active=True,
        )
        user.organisation = org
        user.organisation_id = org.id
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        response = client.get("/BW/activation-choice", follow_redirects=False)

        assert response.status_code == 302
        assert "confirm-subscription" in response.location

    def test_displays_when_subscription_confirmed(self, app: Flask, fresh_db):
        """Activation choice displays when subscription is confirmed."""
        org = Organisation(name="Confirmed Org")
        fresh_db.session.add(org)
        fresh_db.session.commit()

        user = User(
            email=f"confirmed_{uuid.uuid4().hex[:8]}@example.com",
            first_name="Confirmed",
            last_name="User",
            active=True,
        )
        user.organisation = org
        user.organisation_id = org.id
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        # Set session to indicate subscription is confirmed
        with client.session_transaction() as sess:
            sess["bw_type_confirmed"] = True
            sess["bw_type"] = "media"

        response = client.get("/BW/activation-choice")

        assert response.status_code == 200


# -----------------------------------------------------------------------------
# Tests: Information route
# -----------------------------------------------------------------------------


class TestInformation:
    """E2E tests for GET /BW/information."""

    def test_displays_bw_information(self, app: Flask, fresh_db):
        """Information page displays BW details for owner."""
        data = create_bw_test_data(fresh_db)
        client = make_authenticated_client(app, data["media_owner"])

        response = client.get("/BW/information")

        assert response.status_code == 200

    def test_redirects_when_no_bw(self, app: Flask, fresh_db):
        """Information redirects to not-authorized if user has no BW."""
        org = Organisation(name="No BW Org")
        fresh_db.session.add(org)
        fresh_db.session.commit()

        user = User(
            email=f"noinfo_{uuid.uuid4().hex[:8]}@example.com",
            first_name="No",
            last_name="Info",
            active=True,
        )
        user.organisation = org
        user.organisation_id = org.id
        fresh_db.session.add(user)
        fresh_db.session.commit()

        client = make_authenticated_client(app, user)

        response = client.get("/BW/information", follow_redirects=False)

        assert response.status_code == 302
        assert (
            "not-authorized" in response.location
            or "not_authorized" in response.location
        )
