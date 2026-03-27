# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Business Wall user_utils module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

from app.models.auth import User
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

    def test_returns_default_logo_for_inactive_org(self, db_session: Session):
        """Should return default logo for inactive/AUTO organisation."""
        org = Organisation(
            name="Test Inactive Org",
            active=False,
        )
        db_session.add(org)
        db_session.flush()

        result = get_organisation_logo_url(org)

        assert result == "/static/img/logo-page-non-officielle.png"

    def test_returns_default_logo_when_no_bw(self, db_session: Session):
        """Should return default logo when org has no BusinessWall."""
        org = Organisation(
            name="Test Org",
        )
        db_session.add(org)
        db_session.flush()

        result = get_organisation_logo_url(org)

        assert result == "/static/img/logo-page-non-officielle.png"

    def test_returns_default_logo_for_non_active_bw(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return default logo when BW is not active (e.g., DRAFT)."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_organisation_logo_url(test_org)

        assert result == "/static/img/logo-page-non-officielle.png"

    def test_returns_bw_logo_when_active_bw_exists(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return BW logo when active BusinessWall exists."""
        test_org.active = True
        db_session.flush()

        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        test_org.bw_id = bw.id
        test_org.bw_active = bw.bw_type
        db_session.flush()

        # Mock the BW logo URL
        expected_logo_url = "https://mocked.com/bw-logo.png"
        with mock.patch.object(
            bw, "logo_image_signed_url", return_value=expected_logo_url
        ):
            result = get_organisation_logo_url(test_org)

        assert result == expected_logo_url


class TestGetActiveBusinessWallForOrganisation:
    """Tests for get_active_business_wall_for_organisation function."""

    def test_returns_none_when_no_business_wall(self, db_session: Session):
        """Should return None when organisation has no BusinessWall."""
        org = Organisation(
            name="Test Org",
        )
        db_session.add(org)
        db_session.flush()

        result = get_active_business_wall_for_organisation(org)

        assert result is None

    def test_returns_active_business_wall(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return active BusinessWall for organisation."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        # Link organisation to BW
        test_org.bw_id = bw.id
        db_session.flush()

        result = get_active_business_wall_for_organisation(test_org)

        assert result is not None
        assert result.id == bw.id
        assert result.status == BWStatus.ACTIVE.value

    def test_returns_none_for_draft_business_wall(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return None for draft BusinessWall (not active)."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_active_business_wall_for_organisation(test_org)

        assert result is None

    def test_returns_none_for_suspended_business_wall(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return None for suspended BusinessWall (not active)."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.SUSPENDED.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_active_business_wall_for_organisation(test_org)

        assert result is None

    def test_returns_none_for_cancelled_business_wall(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return None when only BusinessWall is cancelled."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_active_business_wall_for_organisation(test_org)

        assert result is None

    def test_returns_most_recent_active_bw(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return the most recent non-cancelled BusinessWall."""
        # Create older active BW
        old_bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(old_bw)
        db_session.flush()

        # Create newer active BW
        new_bw = BusinessWall(
            bw_type=BWType.PR.value,
            status=BWStatus.ACTIVE.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(new_bw)
        db_session.flush()

        # Link organisation to newest BW
        test_org.bw_id = new_bw.id
        db_session.flush()

        result = get_active_business_wall_for_organisation(test_org)

        assert result is not None
        assert result.id == new_bw.id
        assert result.bw_type == BWType.PR.value

    def test_skips_cancelled_returns_active(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should skip cancelled BWs and return the active one."""
        # Create cancelled BW (older)
        cancelled_bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(cancelled_bw)
        db_session.flush()

        # Create active BW (newer)
        active_bw = BusinessWall(
            bw_type=BWType.PR.value,
            status=BWStatus.ACTIVE.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(active_bw)
        db_session.flush()

        # Link organisation to active BW
        test_org.bw_id = active_bw.id
        db_session.flush()

        result = get_active_business_wall_for_organisation(test_org)

        assert result is not None
        assert result.id == active_bw.id


class TestGetAnyBusinessWallForOrganisation:
    """Tests for get_any_business_wall_for_organisation function."""

    def test_returns_none_when_no_business_wall(self, db_session: Session):
        """Should return None when organisation has no BusinessWall."""
        org = Organisation(
            name="Test Org",
        )
        db_session.add(org)
        db_session.flush()

        result = get_any_business_wall_for_organisation(org)

        assert result is None

    def test_returns_cancelled_business_wall(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return cancelled BusinessWall (including cancelled)."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(test_org)

        assert result is not None
        assert result.id == bw.id
        assert result.status == BWStatus.CANCELLED.value

    def test_returns_active_business_wall(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return active BusinessWall."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(test_org)

        assert result is not None
        assert result.id == bw.id
        assert result.status == BWStatus.ACTIVE.value

    def test_returns_most_recent_any_bw(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return the most recent BusinessWall regardless of status."""
        old_bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(old_bw)
        db_session.flush()

        new_bw = BusinessWall(
            bw_type=BWType.PR.value,
            status=BWStatus.CANCELLED.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(new_bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(test_org)

        assert result is not None
        assert result.id == new_bw.id
        assert result.status == BWStatus.CANCELLED.value

    def test_returns_draft_business_wall(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return draft BusinessWall (any status)."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(test_org)

        assert result is not None
        assert result.status == BWStatus.DRAFT.value

    def test_returns_suspended_business_wall(
        self, db_session: Session, test_org: Organisation, test_user_owner: User
    ):
        """Should return suspended BusinessWall (any status)."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.SUSPENDED.value,
            owner_id=test_user_owner.id,
            payer_id=test_user_owner.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_any_business_wall_for_organisation(test_org)

        assert result is not None
        assert result.status == BWStatus.SUSPENDED.value


class TestGetBusinessWallForUser:
    """Tests for get_business_wall_for_user function."""

    def test_returns_none_when_user_has_no_organisation(self, test_user_no_org: User):
        """Should return None when user has no organisation."""
        result = get_business_wall_for_user(test_user_no_org)

        assert result is None

    def test_returns_bw_when_user_has_organisation(
        self,
        db_session: Session,
        test_org: Organisation,
        test_user_with_profile: User,
    ):
        """Should return BW when user's organisation has one."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            owner_id=test_user_with_profile.id,
            payer_id=test_user_with_profile.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        # Link organisation to BW
        test_org.bw_id = bw.id
        db_session.flush()

        result = get_business_wall_for_user(test_user_with_profile)

        assert result is not None
        assert result.id == bw.id

    def test_returns_none_for_cancelled_bw(
        self,
        db_session: Session,
        test_org: Organisation,
        test_user_with_profile: User,
    ):
        """Should return None when user's only BW is cancelled."""
        bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.CANCELLED.value,
            owner_id=test_user_with_profile.id,
            payer_id=test_user_with_profile.id,
            organisation_id=test_org.id,
        )
        db_session.add(bw)
        db_session.flush()

        result = get_business_wall_for_user(test_user_with_profile)

        assert result is None


class TestGuessBestBwType:
    """Tests for guess_best_bw_type function."""

    def test_media_for_pm_dir(self, test_user_pm_dir: User):
        """Should return MEDIA for PM_DIR profile."""
        result = guess_best_bw_type(test_user_pm_dir)

        assert result == BWType.MEDIA

    def test_pr_for_pr_dir(self, test_user_pr_dir: User):
        """Should return PR for PR_DIR profile."""
        result = guess_best_bw_type(test_user_pr_dir)

        assert result == BWType.PR

    def test_academics_for_ac_dir(self, test_user_ac_dir: User):
        """Should return ACADEMICS for AC_DIR profile."""
        result = guess_best_bw_type(test_user_ac_dir)

        assert result == BWType.ACADEMICS

    def test_transformers_for_tp_dir_org(self, test_user_tp_dir_org: User):
        """Should return TRANSFORMERS for TP_DIR_ORG profile."""
        result = guess_best_bw_type(test_user_tp_dir_org)

        assert result == BWType.TRANSFORMERS

    def test_default_to_media_for_unknown_profile(
        self, test_user_unknown_profile: User
    ):
        """Should default to MEDIA for unknown profile."""
        result = guess_best_bw_type(test_user_unknown_profile)

        assert result == BWType.MEDIA
