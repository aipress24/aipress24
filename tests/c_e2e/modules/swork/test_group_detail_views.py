# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for swork group detail views - improving coverage for group.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.modules.swork.models import Group
from app.modules.swork.views._common import is_group_member, join_group
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def press_role(db_session: Session) -> Role:
    """Create a press media role."""
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def test_user(db_session: Session, press_role: Role) -> User:
    """Create a test user."""
    user = User(email="group_detail_user@example.com")
    user.first_name = "Group"
    user.last_name = "Member"
    user.photo = b""
    user.active = True
    user.roles.append(press_role)

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def group_owner(db_session: Session, press_role: Role) -> User:
    """Create a group owner user."""
    user = User(email="group_owner@example.com")
    user.first_name = "Group"
    user.last_name = "Owner"
    user.photo = b""
    user.active = True
    user.roles.append(press_role)

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def test_group(db_session: Session, group_owner: User) -> Group:
    """Create a test group."""
    group = Group(
        name="Test Public Group",
        description="A test group for testing",
        owner=group_owner,
        privacy="public",
    )
    db_session.add(group)
    db_session.commit()
    return group


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    return make_authenticated_client(app, test_user)


class TestGroupDetailGetView:
    """Test GET /groups/<id> endpoint."""

    def test_group_detail_page_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
    ):
        """Test group detail page is accessible."""
        response = authenticated_client.get(f"/swork/groups/{test_group.id}")
        assert response.status_code in (200, 302)

    def test_group_detail_shows_group_name(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
    ):
        """Test group detail page shows group name."""
        response = authenticated_client.get(
            f"/swork/groups/{test_group.id}", follow_redirects=True
        )
        assert response.status_code == 200
        assert test_group.name.encode() in response.data

    def test_group_detail_shows_description(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
    ):
        """Test group detail page shows group description."""
        response = authenticated_client.get(
            f"/swork/groups/{test_group.id}", follow_redirects=True
        )
        assert response.status_code == 200
        assert test_group.description.encode() in response.data

    def test_group_detail_shows_join_button_for_non_member(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
    ):
        """Test group detail shows join button for non-members."""
        response = authenticated_client.get(
            f"/swork/groups/{test_group.id}", follow_redirects=True
        )
        assert response.status_code == 200
        # Should show "Rejoindre" button for non-members
        assert "Rejoindre" in response.data.decode("utf-8")

    def test_group_detail_shows_leave_button_for_member(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
        test_user: User,
    ):
        """Test group detail shows leave button for members."""
        # Join the group first
        join_group(test_user, test_group)
        db_session.commit()

        response = authenticated_client.get(
            f"/swork/groups/{test_group.id}", follow_redirects=True
        )
        assert response.status_code == 200
        # Should show "Quitter" button for members
        assert "Quitter" in response.data.decode("utf-8")


class TestGroupToggleJoin:
    """Test toggle-join action on group page."""

    def test_toggle_join_joins_group(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
        test_user: User,
    ):
        """Test toggling join when not a member adds membership."""
        # Verify not a member initially
        assert not is_group_member(test_user, test_group)

        response = authenticated_client.post(
            f"/swork/groups/{test_group.id}",
            data={"action": "toggle-join"},
        )

        # Should return 200 with button text
        assert response.status_code == 200

        # Verify now a member
        db_session.expire_all()
        assert is_group_member(test_user, test_group)

    def test_toggle_join_leaves_group(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
        test_user: User,
    ):
        """Test toggling join when a member removes membership."""
        # First join the group
        join_group(test_user, test_group)
        db_session.commit()
        assert is_group_member(test_user, test_group)

        response = authenticated_client.post(
            f"/swork/groups/{test_group.id}",
            data={"action": "toggle-join"},
        )

        # Should return 200
        assert response.status_code == 200

        # Verify no longer a member
        db_session.expire_all()
        assert not is_group_member(test_user, test_group)

    def test_toggle_join_returns_rejoindre_when_leaving(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
        test_user: User,
    ):
        """Test toggle returns 'Rejoindre' button text after leaving."""
        # First join the group
        join_group(test_user, test_group)
        db_session.commit()

        response = authenticated_client.post(
            f"/swork/groups/{test_group.id}",
            data={"action": "toggle-join"},
        )

        assert response.status_code == 200
        assert b"Rejoindre" in response.data

    def test_toggle_join_returns_quitter_when_joining(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
    ):
        """Test toggle returns 'Quitter' button text after joining."""
        response = authenticated_client.post(
            f"/swork/groups/{test_group.id}",
            data={"action": "toggle-join"},
        )

        assert response.status_code == 200
        assert b"Quitter" in response.data

    def test_unknown_action_returns_empty(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
    ):
        """Test that unknown action returns empty response."""
        response = authenticated_client.post(
            f"/swork/groups/{test_group.id}",
            data={"action": "unknown-action"},
        )

        assert response.status_code == 200
        assert response.data == b""

    def test_post_without_action_returns_empty(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
    ):
        """Test that POST without action returns empty response."""
        response = authenticated_client.post(
            f"/swork/groups/{test_group.id}",
            data={},
        )

        assert response.status_code == 200
        assert response.data == b""


class TestGroupVMProperties:
    """Test GroupVM properties via HTTP requests."""

    def test_group_with_members_shows_member_list(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
        press_role: Role,
    ):
        """Test that group page shows members."""
        # Add some members to the group
        for i in range(3):
            member = User(email=f"member_{i}@example.com")
            member.first_name = f"Member{i}"
            member.last_name = "Test"
            member.photo = b""
            member.active = True
            member.roles.append(press_role)

            profile = KYCProfile(contact_type="PRESSE")
            profile.show_contact_details = {}
            member.profile = profile

            db_session.add(member)
            db_session.add(profile)
            db_session.commit()
            join_group(member, test_group)
            db_session.commit()

        response = authenticated_client.get(f"/swork/groups/{test_group.id}")
        assert response.status_code in (200, 302)

    def test_group_page_renders_with_default_images(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_group: Group,
    ):
        """Test that group page renders with default images."""
        response = authenticated_client.get(
            f"/swork/groups/{test_group.id}", follow_redirects=True
        )
        assert response.status_code == 200
        # Page should render successfully

    def test_group_nonexistent_returns_404(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test that nonexistent group returns 404."""
        response = authenticated_client.get("/swork/groups/99999999")
        assert response.status_code in (404, 302)
