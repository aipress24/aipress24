# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Business Wall user_utils module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums import OrganisationTypeEnum, ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models.business_wall import (
    BusinessWall,
    BWStatus,
    BWType,
)
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
    get_any_business_wall_for_organisation,
    get_business_wall_for_user,
    get_organisation_logo_url,
    guess_best_bw_type,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestGetOrganisationLogoUrl:
    """Tests for get_organisation_logo_url function."""

    def test_returns_default_logo_for_auto_org(self, db_session: Session):
        """Should return default logo for AUTO organisation."""
        org = Organisation(
            name="Test Auto Org",
            type=OrganisationTypeEnum.AUTO,
        )
        db_session.add(org)
        db_session.flush()

        result = get_organisation_logo_url(org)

        assert result == "/static/img/logo-page-non-officielle.png"

    def test_returns_default_logo_when_no_bw(self, db_session: Session):
        """Should return default logo when org has no BusinessWall."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.MEDIA,
        )
        db_session.add(org)
        db_session.flush()

        result = get_organisation_logo_url(org)

        assert result == "/static/img/logo-page-non-officielle.png"

    def test_returns_default_logo_for_non_active_bw(self, db_session: Session):
        """Should return default logo when BW is not active (e.g., DRAFT)."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.MEDIA,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_organisation_logo_url(org)

        assert result == "/static/img/logo-page-non-officielle.png"

    def test_returns_bw_logo_when_active_bw_exists(self, db_session: Session):
        """Should return BW logo when active BusinessWall exists."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.MEDIA,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_organisation_logo_url(org)

        assert result != "/static/img/logo-page-non-officielle.png"


class TestGetActiveBusinessWallForOrganisation:
    """Tests for get_active_business_wall_for_organisation function."""

    def test_returns_none_when_no_business_wall(self, db_session: Session):
        """Should return None when organisation has no BusinessWall."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        result = get_active_business_wall_for_organisation(org)

        assert result is None

    def test_returns_active_business_wall(self, db_session: Session):
        """Should return active BusinessWall for organisation."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_active_business_wall_for_organisation(org)

        assert result is not None
        assert result.id == bw.id
        assert result.status == BWStatus.ACTIVE.value

    def test_returns_none_for_draft_business_wall(self, db_session: Session):
        """Should return None for draft BusinessWall (not active)."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_active_business_wall_for_organisation(org)

        assert result is None

    def test_returns_none_for_suspended_business_wall(self, db_session: Session):
        """Should return None for suspended BusinessWall (not active)."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.SUSPENDED.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_active_business_wall_for_organisation(org)

        assert result is None

    def test_returns_none_for_cancelled_business_wall(self, db_session: Session):
        """Should return None when only BusinessWall is cancelled."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_active_business_wall_for_organisation(org)

        assert result is None

    def test_returns_most_recent_active_bw(self, db_session: Session):
        """Should return the most recent non-cancelled BusinessWall."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        # Create older active BW
        old_bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(old_bw)
        db_session.flush()

        # Create newer active BW
        new_bw = BusinessWall(
            bw_type=BWType.PR.value,
            status=BWStatus.ACTIVE.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(new_bw)
        db_session.flush()

        result = get_active_business_wall_for_organisation(org)

        assert result is not None
        assert result.id == new_bw.id
        assert result.bw_type == BWType.PR.value

    def test_skips_cancelled_returns_active(self, db_session: Session):
        """Should skip cancelled BWs and return the active one."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        # Create cancelled BW (older)
        cancelled_bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(cancelled_bw)
        db_session.flush()

        # Create active BW (newer)
        active_bw = BusinessWall(
            bw_type=BWType.PR.value,
            status=BWStatus.ACTIVE.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(active_bw)
        db_session.flush()

        result = get_active_business_wall_for_organisation(org)

        assert result is not None
        assert result.id == active_bw.id


class TestGetAnyBusinessWallForOrganisation:
    """Tests for get_any_business_wall_for_organisation function."""

    def test_returns_none_when_no_business_wall(self, db_session: Session):
        """Should return None when organisation has no BusinessWall."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        result = get_any_business_wall_for_organisation(org)

        assert result is None

    def test_returns_cancelled_business_wall(self, db_session: Session):
        """Should return cancelled BusinessWall (including cancelled)."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(org)

        assert result is not None
        assert result.id == bw.id
        assert result.status == BWStatus.CANCELLED.value

    def test_returns_active_business_wall(self, db_session: Session):
        """Should return active BusinessWall."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(org)

        assert result is not None
        assert result.id == bw.id
        assert result.status == BWStatus.ACTIVE.value

    def test_returns_most_recent_any_bw(self, db_session: Session):
        """Should return the most recent BusinessWall regardless of status."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        old_bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(old_bw)
        db_session.flush()

        new_bw = BusinessWall(
            bw_type=BWType.PR.value,
            status=BWStatus.CANCELLED.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(new_bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(org)

        assert result is not None
        assert result.id == new_bw.id
        assert result.status == BWStatus.CANCELLED.value

    def test_returns_draft_business_wall(self, db_session: Session):
        """Should return draft BusinessWall (any status)."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(org)

        assert result is not None
        assert result.status == BWStatus.DRAFT.value

    def test_returns_suspended_business_wall(self, db_session: Session):
        """Should return suspended BusinessWall (any status)."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.SUSPENDED.value,
            owner_id=1,
            payer_id=1,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(org)

        assert result is not None
        assert result.status == BWStatus.SUSPENDED.value


class TestGetBusinessWallForUser:
    """Tests for get_business_wall_for_user function."""

    def test_returns_none_when_user_has_no_organisation(self, db_session: Session):
        """Should return None when user has no organisation."""
        user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.flush()

        result = get_business_wall_for_user(user)

        assert result is None

    def test_returns_bw_when_user_has_organisation(self, db_session: Session):
        """Should return BW when user's organisation has one."""
        org = Organisation(
            name="Test Org",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        user = User(
            email="test-bw-user1@example.com",
            first_name="Test",
            last_name="User",
            organisation_id=org.id,
        )
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_code=ProfileEnum.PM_DIR.name,
        )
        db_session.add(profile)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_business_wall_for_user(user)

        assert result is not None
        assert result.id == bw.id

    def test_returns_none_for_cancelled_bw(self, db_session: Session):
        """Should return None when user's only BW is cancelled."""
        org = Organisation(
            name="Test Org 2",
            type=OrganisationTypeEnum.AGENCY,
        )
        db_session.add(org)
        db_session.flush()

        user = User(
            email="test-bw-user2@example.com",
            first_name="Test",
            last_name="User",
            organisation_id=org.id,
        )
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_code=ProfileEnum.PM_DIR.name,
        )
        db_session.add(profile)
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_business_wall_for_user(user)

        assert result is None


class TestGuessBestBwType:
    """Tests for guess_best_bw_type function."""

    def test_media_for_pm_dir(self, db_session: Session):
        """Should return MEDIA for PM_DIR profile."""
        user = User(
            email="test-bw-user4@example.com",
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_code=ProfileEnum.PM_DIR.name,
        )
        db_session.add(profile)
        db_session.flush()

        result = guess_best_bw_type(user)

        assert result == BWType.MEDIA

    def test_pr_for_pr_dir(self, db_session: Session):
        """Should return PR for PR_DIR profile."""
        user = User(
            email="test-bw-user5@example.com",
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_code=ProfileEnum.PR_DIR.name,
        )
        db_session.add(profile)
        db_session.flush()

        result = guess_best_bw_type(user)

        assert result == BWType.PR

    def test_academics_for_ac_dir(self, db_session: Session):
        """Should return ACADEMICS for AC_DIR profile."""
        user = User(
            email="test-bw-user6@example.com",
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_code=ProfileEnum.AC_DIR.name,
        )
        db_session.add(profile)
        db_session.flush()

        result = guess_best_bw_type(user)

        assert result == BWType.ACADEMICS

    def test_transformers_for_tp_dir_org(self, db_session: Session):
        """Should return TRANSFORMERS for TP_DIR_ORG profile."""
        user = User(
            email="test-bw-user7@example.com",
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_code=ProfileEnum.TP_DIR_ORG.name,
        )
        db_session.add(profile)
        db_session.flush()

        result = guess_best_bw_type(user)

        assert result == BWType.TRANSFORMERS

    def test_default_to_media_for_unknown_profile(self, db_session: Session):
        """Should default to MEDIA for unknown profile."""
        user = User(
            email="test-bw-user8@example.com",
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_code="UNKNOWN_PROFILE",
        )
        db_session.add(profile)
        db_session.flush()

        result = guess_best_bw_type(user)

        assert result == BWType.MEDIA
