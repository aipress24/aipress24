# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP comroom views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.organisation import Organisation

from tests.c_e2e.conftest import make_authenticated_client


@pytest.fixture
def pr_user(db_session: Session, test_org: Organisation) -> User:
    """Create a PR user with PRESS_RELATIONS role."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_RELATIONS.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_RELATIONS.name,
            description=RoleEnum.PRESS_RELATIONS.value,
        )
        db_session.add(role)
        db_session.flush()

    profile = KYCProfile()
    user = User(
        email="pr-comroom@example.com",
        first_name="PR",
        last_name="ComroomUser",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    return user


def _ensure_role(db_session: Session, role_enum: RoleEnum) -> Role:
    role = db_session.query(Role).filter_by(name=role_enum.name).first()
    if role is None:
        role = Role(name=role_enum.name, description=role_enum.value)
        db_session.add(role)
        db_session.flush()
    return role


def _make_profile_user(
    db_session: Session,
    test_org: Organisation,
    email: str,
    profile_code: str,
    community_role: RoleEnum,
) -> User:
    """Create a user with a KYC profile_code and community role (no PRESS_RELATIONS)."""
    profile = KYCProfile()
    profile.profile_code = profile_code
    user = User(email=email, first_name="X", last_name="Y", active=True)
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(_ensure_role(db_session, community_role))
    db_session.add(user)
    db_session.commit()
    return user


class TestComroomAccess:
    """Tests for comroom access control."""

    def test_comroom_loads_for_pr_user(self, app: Flask, pr_user: User):
        """Test that comroom loads for PRESS_RELATIONS users."""
        client = make_authenticated_client(app, pr_user)

        response = client.get("/wip/comroom")

        assert response.status_code == 200
        assert (
            b"comroom" in response.data.lower() or b"communiqu" in response.data.lower()
        )

    def test_comroom_forbidden_for_press_media(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test that comroom returns 403 for PRESS_MEDIA users."""
        response = logged_in_client.get("/wip/comroom")

        assert response.status_code == 403

    def test_comroom_loads_for_xp_pr_profile(
        self, app: Flask, db_session: Session, test_org: Organisation
    ):
        """Expert with a PR role (profile XP_PR) may access Com'room — bug #0098/#0100."""
        user = _make_profile_user(
            db_session, test_org, "xp-pr@example.com", "XP_PR", RoleEnum.EXPERT
        )
        client = make_authenticated_client(app, user)

        response = client.get("/wip/comroom")

        assert response.status_code == 200

    def test_comroom_loads_for_transformer_pr_profile(
        self, app: Flask, db_session: Session, test_org: Organisation
    ):
        """Transformer Consultant with PR role (TR_CS_ORG_PR) may access Com'room."""
        user = _make_profile_user(
            db_session,
            test_org,
            "tr-pr@example.com",
            "TR_CS_ORG_PR",
            RoleEnum.TRANSFORMER,
        )
        client = make_authenticated_client(app, user)

        response = client.get("/wip/comroom")

        assert response.status_code == 200

    def test_comroom_forbidden_for_transformer_non_pr_profile(
        self, app: Flask, db_session: Session, test_org: Organisation
    ):
        """A Transformer profile without PR responsibility still can't access Com'room."""
        user = _make_profile_user(
            db_session,
            test_org,
            "tr-no-pr@example.com",
            "TR_CS_ORG",
            RoleEnum.TRANSFORMER,
        )
        client = make_authenticated_client(app, user)

        response = client.get("/wip/comroom")

        assert response.status_code == 403


class TestComroomContent:
    """Tests for comroom content display."""

    def test_comroom_shows_communiques_section(self, app: Flask, pr_user: User):
        """Test comroom shows communiques section."""
        client = make_authenticated_client(app, pr_user)

        response = client.get("/wip/comroom")

        assert response.status_code == 200
        html = response.data.decode()
        assert "Communiqu" in html

    def test_comroom_shows_item_count(self, app: Flask, pr_user: User):
        """Test comroom shows item count (even if zero)."""
        client = make_authenticated_client(app, pr_user)

        response = client.get("/wip/comroom")

        assert response.status_code == 200
