# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for preferences module pages - POST methods and context."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from flask import Flask, g
from flask_login import login_user

from app.enums import OrganisationTypeEnum
from app.models.auth import KYCProfile, User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.preferences.pages.banner import PrefBannerPage
from app.modules.preferences.pages.contact import PrefContactOptionsPage
from app.modules.preferences.pages.interests import PrefInterestsPage
from app.modules.preferences.pages.org_invitation import (
    PrefInvitationsPage,
    organisation_inviting,
    unofficial_organisation,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def make_user_with_profile(db_session: Session, email_prefix: str = "test") -> User:
    """Create a test user with KYC profile using unique email."""
    unique_email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    user = User(email=unique_email)
    user.first_name = "Integration"
    user.last_name = "Test"
    user.photo = b""
    user.active = True

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {"email": True, "phone": False}
    profile.extra = {"hobbies": "reading, coding"}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


def make_organisation(
    db_session: Session,
    name: str = "Test Org",
    org_type: OrganisationTypeEnum = OrganisationTypeEnum.MEDIA,
) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name=f"{name}_{uuid.uuid4().hex[:8]}", type=org_type)
    db_session.add(org)
    db_session.flush()
    return org


def make_invitation(
    db_session: Session, user: User, organisation: Organisation
) -> Invitation:
    """Create an invitation for the test user."""
    inv = Invitation(
        email=user.email,
        organisation_id=organisation.id,
    )
    db_session.add(inv)
    db_session.flush()
    return inv


class TestPrefBannerPageContext:
    """Test PrefBannerPage context method."""

    def test_context_returns_image_url(self, app: Flask, db_session: Session):
        """Test context returns current_image_url."""
        user = make_user_with_profile(db_session, "banner_ctx")
        with app.test_request_context("/preferences/banner"):
            g.user = user
            page = PrefBannerPage()
            ctx = page.context()

            assert isinstance(ctx, dict)
            assert "current_image_url" in ctx

    def test_get_cover_image_url(self, app: Flask, db_session: Session):
        """Test get_cover_image_url method."""
        user = make_user_with_profile(db_session, "banner_url")
        with app.test_request_context("/preferences/banner"):
            g.user = user
            page = PrefBannerPage()
            url = page.get_cover_image_url()

            # URL should be a string (may be empty or signed URL)
            assert isinstance(url, str)


class TestPrefBannerPagePost:
    """Test PrefBannerPage post method."""

    def test_post_cancel_redirects(self, app: Flask, db_session: Session):
        """Test post with cancel action redirects."""
        user = make_user_with_profile(db_session, "banner_cancel")
        with app.test_request_context(
            "/preferences/banner",
            method="POST",
            data={"submit": "cancel"},
        ):
            login_user(user)
            g.user = user
            page = PrefBannerPage()
            response = page.post()

            assert response.status_code == 302
            assert "banner" in response.location

    def test_post_without_image_redirects(self, app: Flask, db_session: Session):
        """Test post without image file redirects."""
        user = make_user_with_profile(db_session, "banner_noimg")
        with app.test_request_context(
            "/preferences/banner",
            method="POST",
            data={},
        ):
            login_user(user)
            g.user = user
            page = PrefBannerPage()
            response = page.post()

            assert response.status_code == 302

    def test_post_unauthenticated_raises(self, app: Flask, db_session: Session):
        """Test post without authentication raises ValueError."""
        user = make_user_with_profile(db_session, "banner_unauth")
        with app.test_request_context(
            "/preferences/banner",
            method="POST",
            data={},
        ):
            g.user = user
            page = PrefBannerPage()

            with pytest.raises(ValueError, match="No currently authenticated user"):
                page.post()


class TestPrefContactOptionsPagePost:
    """Test PrefContactOptionsPage post method."""

    def test_post_cancel_redirects(self, app: Flask, db_session: Session):
        """Test post with cancel action redirects."""
        user = make_user_with_profile(db_session, "contact_cancel")
        with app.test_request_context(
            "/preferences/contact-options",
            method="POST",
            data={"submit": "cancel"},
        ):
            login_user(user)
            g.user = user
            page = PrefContactOptionsPage()
            response = page.post()

            assert response.status_code == 302
            assert "contact-options" in response.location

    def test_post_unauthenticated_raises(self, app: Flask, db_session: Session):
        """Test post without authentication raises ValueError."""
        user = make_user_with_profile(db_session, "contact_unauth")
        with app.test_request_context(
            "/preferences/contact-options",
            method="POST",
            data={},
        ):
            g.user = user
            page = PrefContactOptionsPage()

            with pytest.raises(ValueError, match="No currently authenticated user"):
                page.post()


class TestPrefInterestsPageContext:
    """Test PrefInterestsPage context method."""

    def test_context_returns_hobbies(self, app: Flask, db_session: Session):
        """Test context returns hobbies from profile."""
        user = make_user_with_profile(db_session, "interests_ctx")
        with app.test_request_context("/preferences/interests"):
            g.user = user
            page = PrefInterestsPage()
            ctx = page.context()

            assert isinstance(ctx, dict)
            assert "hobbies" in ctx


class TestPrefInterestsPagePost:
    """Test PrefInterestsPage post method."""

    def test_post_cancel_redirects(self, app: Flask, db_session: Session):
        """Test post with cancel action redirects."""
        user = make_user_with_profile(db_session, "interests_cancel")
        with app.test_request_context(
            "/preferences/interests",
            method="POST",
            data={"submit": "cancel"},
        ):
            login_user(user)
            g.user = user
            page = PrefInterestsPage()
            response = page.post()

            assert response.status_code == 302
            assert "interests" in response.location

    def test_post_unauthenticated_raises(self, app: Flask, db_session: Session):
        """Test post without authentication raises ValueError."""
        user = make_user_with_profile(db_session, "interests_unauth")
        with app.test_request_context(
            "/preferences/interests",
            method="POST",
            data={},
        ):
            g.user = user
            page = PrefInterestsPage()

            with pytest.raises(ValueError, match="No currently authenticated user"):
                page.post()


class TestOrganisationInvitingFunction:
    """Test organisation_inviting helper function."""

    def test_returns_empty_list_without_invitations(
        self, app: Flask, db_session: Session
    ):
        """Test returns empty list when user has no invitations."""
        user = make_user_with_profile(db_session, "inv_empty")
        with app.app_context():
            result = organisation_inviting(user)
            assert isinstance(result, list)

    def test_returns_invitations_for_user(self, app: Flask, db_session: Session):
        """Test returns invitation info for user."""
        user = make_user_with_profile(db_session, "inv_list")
        org = make_organisation(db_session)
        make_invitation(db_session, user, org)

        with app.app_context():
            result = organisation_inviting(user)

            assert len(result) >= 1
            org_info = next((r for r in result if r["org_id"] == str(org.id)), None)
            assert org_info is not None
            assert "label" in org_info
            assert "disabled" in org_info

    def test_marks_current_org_as_disabled(self, app: Flask, db_session: Session):
        """Test marks user's current organisation as disabled."""
        user = make_user_with_profile(db_session, "inv_disabled")
        org = make_organisation(db_session)
        make_invitation(db_session, user, org)
        user.organisation_id = org.id
        db_session.flush()

        with app.app_context():
            result = organisation_inviting(user)

            org_info = next((r for r in result if r["org_id"] == str(org.id)), None)
            assert org_info is not None
            assert org_info["disabled"] == "disabled"

    def test_includes_unofficial_organisation(self, app: Flask, db_session: Session):
        """Test includes unofficial (AUTO) organisation if user is member."""
        user = make_user_with_profile(db_session, "inv_auto")
        auto_org = make_organisation(db_session, "Auto Org", OrganisationTypeEnum.AUTO)
        user.organisation_id = auto_org.id
        user.organisation = auto_org
        db_session.flush()

        with app.app_context():
            result = organisation_inviting(user)

            # Should include the AUTO org
            auto_info = next(
                (r for r in result if r["org_id"] == str(auto_org.id)), None
            )
            assert auto_info is not None


class TestUnofficialOrganisationFunction:
    """Test unofficial_organisation helper function."""

    def test_returns_empty_dict_without_org(self, app: Flask, db_session: Session):
        """Test returns empty dict when user has no organisation."""
        user = make_user_with_profile(db_session, "unoff_noorg")
        with app.app_context():
            result = unofficial_organisation(user)
            assert result == {}

    def test_returns_empty_dict_for_official_org(self, app: Flask, db_session: Session):
        """Test returns empty dict for official (non-AUTO) organisation."""
        user = make_user_with_profile(db_session, "unoff_official")
        org = make_organisation(db_session)
        user.organisation_id = org.id
        user.organisation = org
        db_session.flush()

        with app.app_context():
            result = unofficial_organisation(user)
            assert result == {}

    def test_returns_info_for_auto_org(self, app: Flask, db_session: Session):
        """Test returns org info for AUTO organisation."""
        user = make_user_with_profile(db_session, "unoff_auto")
        auto_org = make_organisation(db_session, "Auto Org", OrganisationTypeEnum.AUTO)
        user.organisation_id = auto_org.id
        user.organisation = auto_org
        db_session.flush()

        with app.app_context():
            result = unofficial_organisation(user)

            assert "label" in result
            assert "org_id" in result
            assert result["org_id"] == str(auto_org.id)
            assert result["disabled"] == "disabled"


class TestPrefInvitationsPageContext:
    """Test PrefInvitationsPage context method."""

    def test_context_returns_invitations(self, app: Flask, db_session: Session):
        """Test context returns invitations list."""
        user = make_user_with_profile(db_session, "invpage_ctx")
        with app.test_request_context("/preferences/invitations_page"):
            g.user = user
            page = PrefInvitationsPage()
            ctx = page.context()

            assert isinstance(ctx, dict)
            assert "invitations" in ctx
            assert "open_invitations" in ctx
            assert "unofficial" in ctx
            assert isinstance(ctx["invitations"], list)
            assert isinstance(ctx["open_invitations"], int)

    def test_context_counts_open_invitations(self, app: Flask, db_session: Session):
        """Test context counts non-disabled invitations."""
        user = make_user_with_profile(db_session, "invpage_count")
        org = make_organisation(db_session)
        make_invitation(db_session, user, org)

        with app.test_request_context("/preferences/invitations_page"):
            g.user = user
            page = PrefInvitationsPage()
            ctx = page.context()

            # Should have at least one open invitation
            assert ctx["open_invitations"] >= 1


class TestPrefInvitationsPagePost:
    """Test PrefInvitationsPage post method."""

    def test_post_unknown_action_redirects_home(self, app: Flask, db_session: Session):
        """Test post with unknown action redirects to home."""
        user = make_user_with_profile(db_session, "invpage_unknown")
        with app.test_request_context(
            "/preferences/invitations_page",
            method="POST",
            data={"action": "unknown"},
        ):
            g.user = user
            page = PrefInvitationsPage()
            response = page.post()

            assert response.status_code == 200
            assert "HX-Redirect" in response.headers
