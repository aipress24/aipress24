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

    def test_comroom_loads_for_transformer(
        self, app: Flask, db_session: Session, test_org: Organisation
    ):
        """Any Transformer may access Com'room — bug #0100."""
        user = _make_profile_user(
            db_session,
            test_org,
            "tr@example.com",
            "TR_CS_ORG",
            RoleEnum.TRANSFORMER,
        )
        client = make_authenticated_client(app, user)

        response = client.get("/wip/comroom")

        assert response.status_code == 200

    def test_comroom_loads_for_expert(
        self, app: Flask, db_session: Session, test_org: Organisation
    ):
        """Any Expert may access Com'room."""
        user = _make_profile_user(
            db_session, test_org, "xp@example.com", "XP_ANY", RoleEnum.EXPERT
        )
        client = make_authenticated_client(app, user)

        response = client.get("/wip/comroom")

        assert response.status_code == 200

    def test_comroom_loads_for_academic(
        self, app: Flask, db_session: Session, test_org: Organisation
    ):
        """Any Academic may access Com'room."""
        user = _make_profile_user(
            db_session, test_org, "ac@example.com", "AC_DIR", RoleEnum.ACADEMIC
        )
        client = make_authenticated_client(app, user)

        response = client.get("/wip/comroom")

        assert response.status_code == 200


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


class TestSujetsTileInComroom:
    """Bug #0177 (Erick, 2026-06-02) : « il conviendrait de conserver
    pour les attachés de presse la fonction "Sujets" mais à
    l'intérieur de Com'room. Il y aurait donc deux fonctionnalités :
    Sujets et Communiqués. L'idée, c'est que le module Newsroom soit
    exclusivement réservé aux journalistes. »

    Newsroom stays PRESS_MEDIA-only (cf. #c076b016). Sujets becomes
    accessible to attachés de presse via Comroom — the deposit view
    accepts both Newsroom-eligible and Comroom-eligible users.
    """

    def test_comroom_lists_sujets_tile(
        self,
        app: Flask,
        pr_user: User,
    ):
        client = make_authenticated_client(app, pr_user)
        response = client.get("/wip/comroom")
        assert response.status_code == 200
        body = response.data.decode()
        # The Sujets tile must be present on the Comroom page.
        assert "Sujets" in body, (
            "Comroom must surface a Sujets tile for attachés de "
            "presse (#0177)"
        )
        assert "SujetsWipView" in body or "/wip/sujets" in body, (
            "the Sujets tile must link to /wip/sujets"
        )

    def test_pr_relations_user_can_open_sujets_list(
        self,
        app: Flask,
        pr_user: User,
    ):
        """PRESS_RELATIONS users (attachés de presse) can now open the
        Sujets listing — previously the `SujetsWipView.before_request`
        guard called `user_can_access_newsroom` and refused them."""
        client = make_authenticated_client(app, pr_user)
        response = client.get("/wip/sujets/")
        assert response.status_code == 200, (
            f"PR_RELATIONS user must reach the Sujets list via Comroom "
            f"(#0177), got {response.status_code}"
        )

    def test_user_without_either_room_access_still_forbidden(
        self,
        app: Flask,
        db_session: Session,
    ):
        """A user without PRESS_MEDIA / PRESS_RELATIONS / EXPERT /
        TRANSFORMER / ACADEMIC stays blocked from /wip/sujets/ ."""
        outsider = User(
            email="outsider-sujets@example.com",
            first_name="Out",
            last_name="Sider",
            active=True,
        )
        outsider.photo = b""
        db_session.add(outsider)
        db_session.commit()

        client = make_authenticated_client(app, outsider)
        response = client.get("/wip/sujets/")
        assert response.status_code in (302, 403), (
            f"a role-less user must not reach /wip/sujets/, "
            f"got {response.status_code}"
        )
