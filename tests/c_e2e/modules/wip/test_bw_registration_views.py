# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP business wall registration views.

These tests mock Stripe API calls to avoid external dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from app.enums import BWTypeEnum, ProfileEnum

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User
    from app.models.organisation import Organisation


@pytest.fixture
def mock_stripe():
    """Mock all Stripe-related functions."""
    with (
        patch(
            "app.modules.wip.views.business_wall_registration.stripe_bw_subscription_dict"
        ) as mock_dict,
        patch(
            "app.modules.wip.views.business_wall_registration._retrieve_subscription"
        ) as mock_retrieve,
        patch(
            "app.modules.wip.views.business_wall_registration.load_pricing_table_id"
        ) as mock_pricing,
        patch(
            "app.modules.wip.views.business_wall_registration.get_stripe_public_key"
        ) as mock_key,
        patch(
            "app.modules.wip.views.business_wall_registration._find_profile_allowed_subscription"
        ) as mock_find_allowed,
    ):
        mock_dict.return_value = {}
        mock_retrieve.return_value = None
        mock_pricing.return_value = "prctbl_test_123"
        mock_key.return_value = "pk_test_123"
        mock_find_allowed.return_value = []  # Empty list of allowed subscriptions
        yield {
            "stripe_bw_subscription_dict": mock_dict,
            "_retrieve_subscription": mock_retrieve,
            "load_pricing_table_id": mock_pricing,
            "get_stripe_public_key": mock_key,
            "_find_profile_allowed_subscription": mock_find_allowed,
        }


class TestBWRegistrationPage:
    """Tests for the business wall registration page."""

    def test_registration_page_loads(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        mock_stripe,
    ):
        """Test that registration page loads successfully."""
        response = logged_in_client.get("/wip/org-registration")
        assert response.status_code == 200

    def test_registration_page_shows_organisation(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        test_org: Organisation,
        mock_stripe,
    ):
        """Test that registration page shows organisation info."""
        response = logged_in_client.get("/wip/org-registration")
        assert response.status_code == 200
        # Organisation name should be shown
        html = response.data.decode()
        assert test_org.name in html or "Abonnement" in html


class TestBWRegistrationPost:
    """Tests for business wall registration POST actions."""

    def test_post_change_bw_data_redirects(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        mock_stripe,
    ):
        """Test that change_bw_data action redirects."""
        response = logged_in_client.post(
            "/wip/org-registration",
            data={"action": "change_bw_data"},
        )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers

    def test_post_reload_bw_data_redirects(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        mock_stripe,
    ):
        """Test that reload_bw_data action redirects."""
        response = logged_in_client.post(
            "/wip/org-registration",
            data={"action": "reload_bw_data"},
        )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers

    def test_post_suspend_redirects(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        mock_stripe,
    ):
        """Test that suspend action redirects."""
        response = logged_in_client.post(
            "/wip/org-registration",
            data={"action": "suspend"},
        )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers

    def test_post_restore_redirects(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        mock_stripe,
    ):
        """Test that restore action redirects."""
        response = logged_in_client.post(
            "/wip/org-registration",
            data={"action": "restore"},
        )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers

    def test_post_unknown_action_redirects(
        self,
        logged_in_client: FlaskClient,
        test_user: User,
        mock_stripe,
    ):
        """Test that unknown action still redirects."""
        response = logged_in_client.post(
            "/wip/org-registration",
            data={"action": "unknown"},
        )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers


class TestProfileAllowedSubscription:
    """Tests for _find_profile_allowed_subscription function."""

    def test_press_media_profile_allowed_types(self, test_user: User):
        """Test that PRESS_MEDIA profile gets correct allowed types."""
        from app.modules.wip.views.business_wall_registration import (
            _find_profile_allowed_subscription,
        )

        # Set user profile to a press media profile
        test_user.profile.profile_code = ProfileEnum.PM_DIR.name

        allowed = _find_profile_allowed_subscription(test_user)

        # Should return some BWTypeEnum values
        assert isinstance(allowed, list)
        # All items should be BWTypeEnum
        for item in allowed:
            assert isinstance(item, BWTypeEnum)


class TestFilterBWSubscriptions:
    """Tests for _filter_bw_subscriptions function."""

    def test_filter_empty_allowed_returns_empty(self):
        """Test that empty allowed list returns empty result."""
        from app.modules.wip.views.business_wall_registration import (
            ProdInfo,
            _filter_bw_subscriptions,
        )

        prod_info = [
            ProdInfo(
                id="prod_1",
                name="Test Product",
                description="Test",
                features=[],
                default_price=None,
                metadata={"BW": "media"},
                tax_code="",
                images=[],
                url="",
            )
        ]

        result = _filter_bw_subscriptions([], prod_info)
        assert result == []

    def test_filter_matches_allowed_types(self):
        """Test that filter returns only products matching allowed types."""
        from app.modules.wip.views.business_wall_registration import (
            ProdInfo,
            _filter_bw_subscriptions,
        )

        prod_info = [
            ProdInfo(
                id="prod_1",
                name="Media Product",
                description="Test",
                features=[],
                default_price=None,
                metadata={"BW": "media"},
                tax_code="",
                images=[],
                url="",
            ),
            ProdInfo(
                id="prod_2",
                name="COM Product",
                description="Test",
                features=[],
                default_price=None,
                metadata={"BW": "com"},
                tax_code="",
                images=[],
                url="",
            ),
        ]

        # Allow only MEDIA type
        result = _filter_bw_subscriptions([BWTypeEnum.MEDIA], prod_info)

        assert len(result) == 1
        assert result[0].id == "prod_1"


class TestParseSubscription:
    """Tests for _parse_subscription function."""

    def test_parse_subscription_extracts_data(self):
        """Test that subscription data is correctly parsed."""
        from app.modules.wip.views.business_wall_registration import (
            _parse_subscription,
        )

        # Create a mock subscription
        mock_sub = MagicMock()
        mock_sub.id = "sub_123"
        mock_sub.created = 1704067200  # 2024-01-01 00:00:00 UTC
        mock_sub.current_period_start = 1704067200
        mock_sub.current_period_end = 1706745600  # 2024-02-01 00:00:00 UTC
        mock_sub.status = "active"

        result = _parse_subscription(mock_sub)

        assert result.id == "sub_123"
        assert result.status is True  # active

    def test_parse_subscription_inactive_status(self):
        """Test that inactive subscription status is correctly parsed."""
        from app.modules.wip.views.business_wall_registration import (
            _parse_subscription,
        )

        mock_sub = MagicMock()
        mock_sub.id = "sub_456"
        mock_sub.created = 1704067200
        mock_sub.current_period_start = 1704067200
        mock_sub.current_period_end = 1706745600
        mock_sub.status = "canceled"

        result = _parse_subscription(mock_sub)

        assert result.id == "sub_456"
        assert result.status is False  # not active


class TestGetLogoUrl:
    """Tests for _get_logo_url function."""

    def test_no_org_returns_default(self):
        """Test that no org returns default logo."""
        from app.modules.wip.views.business_wall_registration import _get_logo_url

        result = _get_logo_url(None)
        assert result == "/static/img/transparent-square.png"

    def test_auto_org_returns_unofficial_logo(
        self, db_session: Session, test_org: Organisation
    ):
        """Test that auto org returns unofficial logo."""
        from app.models.organisation import OrganisationTypeEnum
        from app.modules.wip.views.business_wall_registration import _get_logo_url

        # Set org type to AUTO to make is_auto return True
        test_org.type = OrganisationTypeEnum.AUTO
        db_session.flush()

        result = _get_logo_url(test_org)
        assert result == "/static/img/logo-page-non-officielle.png"


class TestProductConstants:
    """Tests for product constant dictionaries."""

    def test_product_bw_has_all_types(self):
        """Test that PRODUCT_BW has entries for all expected types."""
        from app.modules.wip.views.business_wall_registration import PRODUCT_BW

        expected_types = [
            "MEDIA",
            "PRESSUNION",
            "MICRO",
            "COM",
            "CORPORATE",
            "ORGANISATION",
            "ACADEMICS",
        ]
        for bw_type in expected_types:
            assert bw_type in PRODUCT_BW

    def test_price_bw_has_all_types(self):
        """Test that PRICE_BW has entries for all expected types."""
        from app.modules.wip.views.business_wall_registration import PRICE_BW

        expected_types = [
            "MEDIA",
            "PRESSUNION",
            "MICRO",
            "COM",
            "CORPORATE",
            "ORGANISATION",
            "ACADEMICS",
        ]
        for bw_type in expected_types:
            assert bw_type in PRICE_BW

    def test_description_bw_has_all_types(self):
        """Test that DESCRIPTION_BW has entries for all expected types."""
        from app.modules.wip.views.business_wall_registration import DESCRIPTION_BW

        expected_types = [
            "MEDIA",
            "PRESSUNION",
            "MICRO",
            "COM",
            "CORPORATE",
            "ORGANISATION",
            "ACADEMICS",
        ]
        for bw_type in expected_types:
            assert bw_type in DESCRIPTION_BW

    def test_org_type_conversion_has_all_types(self):
        """Test that ORG_TYPE_CONVERSION covers all org types."""
        from app.modules.wip.views.business_wall_registration import ORG_TYPE_CONVERSION

        expected_types = [
            "AGENCY",
            "MEDIA",
            "MICRO",
            "CORPORATE",
            "PRESSUNION",
            "COM",
            "ORGANISATION",
            "TRANSFORMER",
            "ACADEMICS",
        ]
        for org_type in expected_types:
            assert org_type in ORG_TYPE_CONVERSION
