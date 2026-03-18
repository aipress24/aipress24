# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for admin show_user views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.constants import LABEL_COMPTE_DESACTIVE
from app.enums import OrganisationTypeEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.admin.views.show_user import ShowUserView

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _get_or_create_role(db_session: Session, name: str) -> Role:
    """Get existing role or create new one."""
    role = db_session.query(Role).filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=f"{name} role")
        db_session.add(role)
        db_session.flush()
    return role


@pytest.fixture
def organisation(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Org", type=OrganisationTypeEnum.MEDIA)
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def auto_organisation(db_session: Session) -> Organisation:
    """Create an auto-generated organisation."""
    org = Organisation(name="Auto Org", type=OrganisationTypeEnum.AUTO)
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def user_with_org(db_session: Session, organisation: Organisation) -> User:
    """Create a user with an organisation and profile."""
    user = User(
        email="member@example.com",
        first_name="Test",
        last_name="Member",
        active=True,
    )
    user.organisation = organisation
    user.organisation_id = organisation.id
    db_session.add(user)
    db_session.flush()

    # Create KYCProfile for user (required by remove_user_organisation)
    profile = KYCProfile(user_id=user.id, profile_code="PM_DIR", profile_label="Test")
    db_session.add(profile)
    db_session.flush()

    return user


class TestDeactivateProfile:
    """Tests for deactivating user profiles."""

    def test_deactivate_profile_sets_inactive(
        self, app: Flask, db_session: Session, user_with_org: User
    ):
        """Test that deactivating a profile sets user inactive."""
        view = ShowUserView()

        with app.test_request_context():
            view._deactivate_profile(user_with_org)

        assert user_with_org.active is False
        assert user_with_org.validation_status == LABEL_COMPTE_DESACTIVE
        assert user_with_org.validated_at is not None


class TestRemoveOrganisation:
    """Tests for removing user from organisation."""

    def test_remove_organisation_clears_org_id(
        self, app: Flask, db_session: Session, user_with_org: User
    ):
        """Test that removing organisation clears the user's org_id."""
        view = ShowUserView()
        assert user_with_org.organisation_id is not None

        with app.test_request_context():
            view._remove_organisation(user_with_org)

        assert user_with_org.organisation_id is None
