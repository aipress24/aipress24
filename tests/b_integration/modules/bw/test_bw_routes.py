# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Business Wall activation routes.

These tests verify the Flask route handlers work correctly.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from flask import Flask, session
from flask_security import login_user

from app.enums import ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    BWStatus,
    InvitationStatus,
    RoleAssignment,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Media Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_user_media(db_session: Session, test_org: Organisation) -> User:
    """Create a test user with media profile."""
    user = User(
        email=_unique_email(),
        first_name="Media",
        last_name="Director",
        active=True,
    )
    user.organisation = test_org
    user.organisation_id = test_org.id
    db_session.add(user)
    db_session.flush()

    # KYCProfile requires complete JSON fields for metier_fonction to work
    profile = KYCProfile(
        user_id=user.id,
        profile_id="profile_media",
        profile_code=ProfileEnum.PM_DIR.value,
        profile_label="Dirigeant Presse",
        info_personnelle={"metier_principal_detail": ["Director"]},
        match_making={"fonctions_journalisme": ["Directeur de publication"]},
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask,
    db,
    test_user_media: User,
) -> FlaskClient:
    """Create a test client logged in as test user."""
    client = app.test_client()
    with app.test_request_context():
        login_user(test_user_media)
        with client.session_transaction() as sess:
            for key, value in session.items():
                sess[key] = value
    return client


@pytest.fixture
def test_business_wall(
    db_session: Session,
    test_org: Organisation,
    test_user_media: User,
) -> BusinessWall:
    """Create a test Business Wall."""
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=test_user_media.id,
        payer_id=test_user_media.id,
        organisation_id=test_org.id,
    )
    db_session.add(bw)
    db_session.flush()

    owner_role = RoleAssignment(
        business_wall_id=bw.id,
        user_id=test_user_media.id,
        role_type=BWRoleType.BW_OWNER.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
    )
    db_session.add(owner_role)
    db_session.flush()
    return bw


# =============================================================================
# Stage 1: Subscription Confirmation Routes
# =============================================================================


class TestStage1Routes:
    """Tests for Stage 1 routes (subscription confirmation)."""

    def test_index_redirects_to_confirm_subscription(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Index should redirect to confirm subscription for new users."""
        response = authenticated_client.get("/BW/")

        # Should redirect (302 or 303)
        assert response.status_code in (302, 303)
        assert "confirm-subscription" in response.headers.get("Location", "")

    def test_confirm_subscription_renders(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Confirm subscription page should render successfully."""
        response = authenticated_client.get("/BW/confirm-subscription")

        assert response.status_code == 200

    def test_select_subscription_sets_session(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Select subscription should set session and redirect."""
        response = authenticated_client.post(
            "/BW/select-subscription/media",
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)

        # Check session was updated
        with authenticated_client.session_transaction() as sess:
            assert sess.get("bw_type") == "media"
            assert sess.get("bw_type_confirmed") is True

    def test_select_subscription_invalid_type_redirects(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Invalid BW type should redirect to confirm subscription."""
        response = authenticated_client.post(
            "/BW/select-subscription/invalid_type",
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)
        assert "confirm-subscription" in response.headers.get("Location", "")


# =============================================================================
# Stage 2: Contact Nomination Routes
# =============================================================================


class TestStage2Routes:
    """Tests for Stage 2 routes (contact nomination)."""

    def test_nominate_contacts_requires_confirmed_type(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Nominate contacts should redirect if type not confirmed."""
        response = authenticated_client.get("/BW/nominate-contacts")

        assert response.status_code in (302, 303)
        assert "confirm-subscription" in response.headers.get("Location", "")

    def test_nominate_contacts_renders_with_confirmed_type(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Nominate contacts should render when type is confirmed."""
        # First confirm the type
        authenticated_client.post("/BW/select-subscription/media")

        response = authenticated_client.get("/BW/nominate-contacts")

        assert response.status_code == 200

    def test_submit_contacts_stores_data(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Submit contacts should store data in session."""
        # First confirm the type
        authenticated_client.post("/BW/select-subscription/media")

        response = authenticated_client.post(
            "/BW/submit-contacts",
            data={
                "owner_first_name": "Jean",
                "owner_last_name": "Dupont",
                "owner_email": "jean@example.com",
                "owner_phone": "+33612345678",
                "same_as_owner": "on",
            },
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)

        with authenticated_client.session_transaction() as sess:
            assert sess.get("owner_first_name") == "Jean"
            assert sess.get("owner_last_name") == "Dupont"
            assert sess.get("contacts_confirmed") is True
            # Payer should be same as owner
            assert sess.get("payer_first_name") == "Jean"

    def test_submit_contacts_different_payer(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Submit contacts should handle different payer."""
        authenticated_client.post("/BW/select-subscription/media")

        response = authenticated_client.post(
            "/BW/submit-contacts",
            data={
                "owner_first_name": "Jean",
                "owner_last_name": "Dupont",
                "owner_email": "jean@example.com",
                "owner_phone": "+33612345678",
                "payer_first_name": "Marie",
                "payer_last_name": "Martin",
                "payer_email": "marie@example.com",
                "payer_phone": "+33698765432",
            },
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)

        with authenticated_client.session_transaction() as sess:
            assert sess.get("owner_first_name") == "Jean"
            assert sess.get("payer_first_name") == "Marie"


# =============================================================================
# Stage 3: Activation Routes (Free)
# =============================================================================


class TestStage3FreeRoutes:
    """Tests for Stage 3 routes (free activation)."""

    def test_activate_free_page_requires_contacts(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Activate free should redirect if contacts not confirmed."""
        # Confirm type but not contacts
        authenticated_client.post("/BW/select-subscription/media")

        response = authenticated_client.get("/BW/activate-free/media")

        assert response.status_code in (302, 303)
        assert "nominate-contacts" in response.headers.get("Location", "")

    def test_activate_free_page_renders(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Activate free page should render when prerequisites met."""
        # Complete steps 1 and 2
        authenticated_client.post("/BW/select-subscription/media")
        authenticated_client.post(
            "/BW/submit-contacts",
            data={
                "owner_first_name": "Jean",
                "owner_last_name": "Dupont",
                "owner_email": "jean@example.com",
                "owner_phone": "+33612345678",
                "same_as_owner": "on",
            },
        )

        response = authenticated_client.get("/BW/activate-free/media")

        assert response.status_code == 200

    def test_activate_free_invalid_type_redirects(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Invalid or paid type should redirect."""
        response = authenticated_client.get("/BW/activate-free/pr")

        assert response.status_code in (302, 303)

    def test_activate_free_without_cgv_returns_to_page(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Not accepting CGV should return to activation page."""
        # Complete steps 1 and 2
        authenticated_client.post("/BW/select-subscription/media")
        authenticated_client.post(
            "/BW/submit-contacts",
            data={
                "owner_first_name": "Jean",
                "owner_last_name": "Dupont",
                "owner_email": "jean@example.com",
                "owner_phone": "+33612345678",
                "same_as_owner": "on",
            },
        )

        # Submit without cgv_accepted
        response = authenticated_client.post(
            "/BW/activate_free/media",
            data={},
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)
        assert "activate-free" in response.headers.get("Location", "")


# =============================================================================
# Stage 3: Activation Routes (Paid)
# =============================================================================


class TestStage3PaidRoutes:
    """Tests for Stage 3 routes (paid activation)."""

    def test_pricing_page_requires_contacts(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Pricing page should redirect if contacts not confirmed."""
        authenticated_client.post("/BW/select-subscription/pr")

        response = authenticated_client.get("/BW/pricing/pr")

        assert response.status_code in (302, 303)
        assert "nominate-contacts" in response.headers.get("Location", "")

    def test_pricing_page_renders_for_paid_type(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Pricing page should render for paid BW types."""
        # Complete steps 1 and 2 for PR type
        authenticated_client.post("/BW/select-subscription/pr")
        authenticated_client.post(
            "/BW/submit-contacts",
            data={
                "owner_first_name": "Jean",
                "owner_last_name": "Dupont",
                "owner_email": "jean@example.com",
                "owner_phone": "+33612345678",
                "same_as_owner": "on",
            },
        )

        response = authenticated_client.get("/BW/pricing/pr")

        assert response.status_code == 200

    def test_pricing_page_rejects_free_type(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Pricing page should redirect for free types."""
        response = authenticated_client.get("/BW/pricing/media")

        assert response.status_code in (302, 303)

    def test_set_pricing_without_cgv_redirects(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Set pricing without CGV should redirect back."""
        authenticated_client.post("/BW/select-subscription/pr")
        authenticated_client.post(
            "/BW/submit-contacts",
            data={
                "owner_first_name": "Jean",
                "owner_last_name": "Dupont",
                "owner_email": "jean@example.com",
                "owner_phone": "+33612345678",
                "same_as_owner": "on",
            },
        )

        response = authenticated_client.post(
            "/BW/set_pricing/pr",
            data={"client_count": "5"},
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)
        assert "pricing" in response.headers.get("Location", "")

    def test_set_pricing_with_cgv_proceeds_to_payment(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Set pricing with CGV should proceed to payment."""
        authenticated_client.post("/BW/select-subscription/pr")
        authenticated_client.post(
            "/BW/submit-contacts",
            data={
                "owner_first_name": "Jean",
                "owner_last_name": "Dupont",
                "owner_email": "jean@example.com",
                "owner_phone": "+33612345678",
                "same_as_owner": "on",
            },
        )

        response = authenticated_client.post(
            "/BW/set_pricing/pr",
            data={"client_count": "5", "cgv_accepted": "on"},
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)
        assert "payment" in response.headers.get("Location", "")


# =============================================================================
# Dashboard and Post-Activation Routes
# =============================================================================


class TestDashboardRoutes:
    """Tests for dashboard routes."""

    def test_dashboard_requires_activation(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Dashboard should redirect if BW not activated."""
        response = authenticated_client.get("/BW/dashboard")

        assert response.status_code in (302, 303)

    def test_reset_clears_session(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Reset should clear all session data."""
        # Set some session data
        with authenticated_client.session_transaction() as sess:
            sess["bw_type"] = "media"
            sess["bw_activated"] = True

        response = authenticated_client.post(
            "/BW/reset",
            follow_redirects=False,
        )

        assert response.status_code in (302, 303)


# =============================================================================
# Not Authorized Route
# =============================================================================


class TestNotAuthorizedRoute:
    """Tests for not authorized route."""

    def test_not_authorized_renders(
        self,
        authenticated_client: FlaskClient,
    ) -> None:
        """Not authorized page should render."""
        # Set an error message first
        with authenticated_client.session_transaction() as sess:
            sess["error"] = "Test error message"

        response = authenticated_client.get("/BW/not-authorized")

        assert response.status_code == 200
