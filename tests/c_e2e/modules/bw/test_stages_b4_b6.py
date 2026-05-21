# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Business Wall management stages B4-B6.

B4: Manage external partners
B5: Assign missions
B6: Configure content
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import Flask, session
from flask_security import login_user

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User
    from app.models.organisation import Organisation
    from app.modules.bw.bw_activation.models import BusinessWall


class TestStageB4ExternalPartnersRoutes:
    """Tests for Stage B4 routes (external partners management)."""

    def test_manage_external_partners_requires_activation(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """manage-external-partners should redirect if not activated."""
        client = app.test_client()
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        response = client.get("/BW/manage-external-partners")
        assert response.status_code in (302, 303)

    def test_manage_external_partners_renders_when_activated(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """manage-external-partners should render when activated."""
        response = authenticated_owner_client.get("/BW/manage-external-partners")
        assert response.status_code == 200

    def test_failed_pr_invite_surfaces_admin_feedback(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """Audit D2 (#0139-class): a failed `invite_pr_provider` must
        not redirect silently.

        Posting an empty/invalid `pr_provider` makes
        `invite_pr_provider` return False (no PR selected). The route
        used to `redirect(...)` with no flash / session error, so the
        admin got zero feedback and the partnership was silently NOT
        created. The page now flashes an explicit error.
        """
        response = authenticated_owner_client.post(
            "/BW/manage-external-partners",
            data={"pr_provider": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        body = response.data.decode()
        assert "partner-invite-flash" in body, (
            "a failed PR-provider invitation must surface a visible "
            "error to the admin, not redirect silently"
        )


class TestStageB5MissionsRoutes:
    """Tests for Stage B5 routes (missions assignment)."""

    def test_assign_missions_requires_activation(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """assign-missions should redirect if not activated."""
        client = app.test_client()
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        response = client.get("/BW/assign-missions")
        assert response.status_code in (302, 303)

    def test_assign_missions_renders_when_activated(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """assign-missions should render when activated."""
        response = authenticated_owner_client.get("/BW/assign-missions")
        assert response.status_code == 200

    def test_assign_missions_initializes_missions_state(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """assign-missions should initialize missions in session."""
        response = authenticated_owner_client.get("/BW/assign-missions")
        assert response.status_code == 200

        with authenticated_owner_client.session_transaction() as sess:
            assert "missions" in sess


class TestStageB6ContentRoutes:
    """Tests for Stage B6 routes (content configuration)."""

    def test_configure_content_requires_activation(
        self,
        app: Flask,
        db,
        test_user_owner: User,
    ) -> None:
        """configure-content should redirect if not activated."""
        client = app.test_client()
        with app.test_request_context():
            login_user(test_user_owner)
            with client.session_transaction() as sess:
                for key, value in session.items():
                    sess[key] = value

        response = client.get("/BW/configure-content")
        assert response.status_code in (302, 303)

    def test_configure_content_renders_when_activated(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """configure-content should render when activated."""
        response = authenticated_owner_client.get("/BW/configure-content")
        assert response.status_code == 200

    def test_configure_content_leaders_experts_no_duplicate_name_group(
        self,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
        db_session: Session,
    ) -> None:
        """Bug #0099 : pour les BW « leaders_experts » et « transformers »,
        le champ « Groupe ou entité de rattachement » (`name_group`)
        était rendu deux fois — un bloc générique (corporate_media / pr /
        leaders_experts / transformers / academics) et un bloc spécifique
        leaders_experts/transformers. Le second écrasait la valeur du
        premier au POST. Doit n'apparaître qu'une seule fois.

        Note : `fill_session(bw)` côté route écrase `session["bw_type"]`
        avec `bw.bw_type`, donc on modifie le type sur la BW elle-même.
        """
        test_business_wall.bw_type = "leaders_experts"
        db_session.commit()

        response = authenticated_owner_client.get("/BW/configure-content")
        assert response.status_code == 200
        html = response.data.decode()
        assert html.count('name="name_group"') == 1, (
            'name="name_group" doit apparaître exactement une fois '
            "(rendu deux fois = écrasement au POST, cf. bug #0099)"
        )

    def test_configure_content_post_syncs_name_and_bw_name(
        self,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
        test_org: Organisation,
        db_session: Session,
    ) -> None:
        """POST to configure-content updates BW.name and syncs Organisation.bw_name."""
        response = authenticated_owner_client.post(
            "/BW/configure-content",
            data={"name": "My New BW Name"},
            follow_redirects=True,
        )
        assert response.status_code == 200

        db_session.refresh(test_business_wall)
        db_session.refresh(test_org)
        assert test_business_wall.name == "My New BW Name"
        assert test_org.bw_name == "My New BW Name"
