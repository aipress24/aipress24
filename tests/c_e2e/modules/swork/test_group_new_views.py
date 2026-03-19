# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for swork new group views - improving coverage for group_new.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.modules.swork.models import Group
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
    """Create a test user for group creation tests."""
    user = User(email="group_creator@example.com")
    user.first_name = "Group"
    user.last_name = "Creator"
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
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    return make_authenticated_client(app, test_user)


class TestNewGroupGetView:
    """Test GET /groups/new endpoint."""

    def test_new_group_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test new group page is accessible."""
        response = authenticated_client.get("/swork/groups/new")
        assert response.status_code in (200, 302)

    def test_new_group_page_contains_form(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test new group page contains a form."""
        response = authenticated_client.get("/swork/groups/new", follow_redirects=True)
        assert response.status_code == 200
        assert b"<form" in response.data

    def test_new_group_page_has_name_field(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test new group page has name input field."""
        response = authenticated_client.get("/swork/groups/new", follow_redirects=True)
        assert response.status_code == 200
        assert b'name="name"' in response.data

    def test_new_group_page_has_description_field(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test new group page has description input field."""
        response = authenticated_client.get("/swork/groups/new", follow_redirects=True)
        assert response.status_code == 200
        assert b'name="description"' in response.data


class TestNewGroupPostView:
    """Test POST /groups/new endpoint."""

    def test_create_group_with_valid_name(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_user: User,
    ):
        """Test creating a group with valid name succeeds."""
        response = authenticated_client.post(
            "/swork/groups/new",
            data={"name": "Test Group", "description": "A test group description"},
            follow_redirects=False,
        )

        # Should redirect to groups list
        assert response.status_code == 302
        assert "/swork/groups" in response.location

        # Verify group was created
        db_session.expire_all()
        groups = list(db_session.query(Group).filter_by(name="Test Group"))
        assert len(groups) == 1
        assert groups[0].description == "A test group description"
        assert groups[0].owner_id == test_user.id
        assert groups[0].privacy == "public"

    def test_create_group_without_description(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_user: User,
    ):
        """Test creating a group without description succeeds."""
        response = authenticated_client.post(
            "/swork/groups/new",
            data={"name": "Group No Desc", "description": ""},
            follow_redirects=False,
        )

        # Should redirect to groups list
        assert response.status_code == 302

        # Verify group was created
        db_session.expire_all()
        groups = list(db_session.query(Group).filter_by(name="Group No Desc"))
        assert len(groups) == 1
        assert groups[0].description == ""

    def test_create_group_with_empty_name_fails(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test creating a group with empty name fails."""
        response = authenticated_client.post(
            "/swork/groups/new",
            data={"name": "", "description": "Description without name"},
            follow_redirects=False,
        )

        # Should redirect back to new group page
        assert response.status_code == 302
        assert "/swork/groups/new" in response.location

        # Verify no group was created
        db_session.expire_all()
        groups = list(
            db_session.query(Group).filter_by(description="Description without name")
        )
        assert len(groups) == 0

    def test_create_group_with_whitespace_name_fails(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test creating a group with whitespace-only name fails."""
        response = authenticated_client.post(
            "/swork/groups/new",
            data={"name": "   ", "description": "Whitespace name test"},
            follow_redirects=False,
        )

        # Should redirect back to new group page
        assert response.status_code == 302
        assert "/swork/groups/new" in response.location

        # Verify no group was created
        db_session.expire_all()
        groups = list(
            db_session.query(Group).filter_by(description="Whitespace name test")
        )
        assert len(groups) == 0

    def test_create_group_redirects_on_success(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test creating a group redirects to groups list on success."""
        response = authenticated_client.post(
            "/swork/groups/new",
            data={"name": "Flash Success Group", "description": ""},
            follow_redirects=False,
        )

        # Should redirect to groups list
        assert response.status_code == 302
        assert "/swork/groups" in response.location

    def test_create_group_redirects_on_error(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test creating a group with empty name redirects back to form."""
        response = authenticated_client.post(
            "/swork/groups/new",
            data={"name": "", "description": ""},
            follow_redirects=False,
        )

        # Should redirect back to new group form
        assert response.status_code == 302
        assert "/swork/groups/new" in response.location

    def test_create_group_trims_whitespace(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test that group name and description are trimmed."""
        response = authenticated_client.post(
            "/swork/groups/new",
            data={
                "name": "  Trimmed Group  ",
                "description": "  Trimmed description  ",
            },
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Verify group was created with trimmed values
        db_session.expire_all()
        groups = list(db_session.query(Group).filter_by(name="Trimmed Group"))
        assert len(groups) == 1
        assert groups[0].description == "Trimmed description"
