# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Business Wall management stages B1-B3.

B1: Invite organisation members
B2: Manage organisation members
B3: Manage internal roles
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask.testing import FlaskClient

    from app.modules.bw.bw_activation.models import BusinessWall


class TestStageB1InviteOrgMembersRoutes:
    """Tests for Stage B1 routes (invite organisation members)."""

    def test_invite_organisation_members_requires_bw(
        self,
        unauthenticated_bw_client: FlaskClient,
    ) -> None:
        """invite-organisation-members should redirect if no BW exists."""
        response = unauthenticated_bw_client.get("/BW/invite-organisation-members")
        # Should redirect to not-authorized (no BW found)
        assert response.status_code in (302, 303)

    def test_invite_organisation_members_renders_for_owner(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """invite-organisation-members should render for BW owner."""
        response = authenticated_owner_client.get("/BW/invite-organisation-members")
        assert response.status_code == 200

    def test_invitations_modal_harmonised_keeps_wiring(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """Ticket #0142: the "Modifier la liste des invitations" modal
        was harmonised with the BW page card. The visual fix must keep
        all functional wiring (modal id, HTMX action, textarea) and
        drop the readability anti-pattern (a shadowed description box
        nested inside the shadowed modal panel)."""
        body = authenticated_owner_client.get(
            "/BW/invite-organisation-members"
        ).data.decode()

        # Functional wiring intact.
        assert 'id="list_invitations_modal"' in body
        assert 'name="content"' in body
        assert "change_invitations_emails" in body
        assert "/BW/invite-organisation-members" in body
        # Harmonised header present.
        assert "Emails invités (un par ligne)" in body
        # The double-card anti-pattern is gone: the description
        # paragraph no longer carries its own shadow/rounded box.
        assert 'class="bg-white rounded-lg shadow' not in body


class TestStageB2ManageOrgMembersRoutes:
    """Tests for Stage B2 routes (manage organisation members)."""

    def test_manage_organisation_members_requires_bw(
        self,
        unauthenticated_bw_client: FlaskClient,
    ) -> None:
        """manage-organisation-members should redirect if no BW exists."""
        response = unauthenticated_bw_client.get("/BW/manage-organisation-members")
        assert response.status_code in (302, 303)

    def test_manage_organisation_members_renders_for_owner(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """manage-organisation-members should render for BW owner."""
        response = authenticated_owner_client.get("/BW/manage-organisation-members")
        assert response.status_code == 200

    def test_members_modal_harmonised_keeps_wiring(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """Ticket #0142 step 4 (Erick, 2026-05-22) : the « Gérer la
        liste des membres » modal was still on the old interface
        (rounded-lg shadow, dark:bg-gray-700, no inline label) after
        the step 3 harmonisation. Port the same harmonisation pattern
        — visual change must keep all functional wiring (modal id,
        HTMX action, textarea name)."""
        body = authenticated_owner_client.get(
            "/BW/manage-organisation-members"
        ).data.decode()

        # Functional wiring intact.
        assert 'id="list_users_modal"' in body
        assert 'name="content"' in body
        assert "change_emails" in body
        assert "/BW/manage-organisation-members" in body
        # The dark-mode / double-card anti-pattern is gone.
        assert "dark:bg-gray-700" not in body, (
            "old dark-mode container styling must be dropped (#0142/4)"
        )
        # Harmonised header label : explicit field label visible above
        # the textarea (matches B02's « Emails invités (un par ligne) »).
        assert "Emails des membres" in body


class TestStageB3ManageInternalRolesRoutes:
    """Tests for Stage B3 routes (manage internal roles)."""

    def test_manage_internal_roles_requires_bw(
        self,
        unauthenticated_bw_client: FlaskClient,
    ) -> None:
        """manage-internal-roles should redirect if no BW exists."""
        response = unauthenticated_bw_client.get("/BW/manage-internal-roles")
        assert response.status_code in (302, 303)

    def test_manage_internal_roles_renders_for_owner(
        self,
        authenticated_owner_client: FlaskClient,
    ) -> None:
        """manage-internal-roles should render for BW owner."""
        response = authenticated_owner_client.get("/BW/manage-internal-roles")
        assert response.status_code == 200

    def test_manage_internal_roles_shows_role_assignments(
        self,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
    ) -> None:
        """manage-internal-roles should display role assignments."""
        response = authenticated_owner_client.get("/BW/manage-internal-roles")
        assert response.status_code == 200
        # The page should contain some content about roles
        assert b"role" in response.data.lower() or b"BWM" in response.data

    def test_change_bwpri_unknown_email_surfaces_flash(
        self,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
    ) -> None:
        """Bug #0139 v2: posting an unknown e-mail to the BWPRi list
        must flash an admin-readable error on the next render.

        The route used to swallow every failure silently — the admin
        saw « tout va bien » while the invitation had been dropped.
        Now `_flash_invitation_outcomes` posts an `error` flash that
        the B04 template renders inline."""
        response = authenticated_owner_client.post(
            "/BW/manage-internal-roles",
            data={
                "action": "change_bwpri_invitations",
                "content": "ghost@example.com",
            },
            follow_redirects=False,
        )
        # HTMX redirect via HX-Redirect header; the body is empty.
        assert response.status_code == 200
        assert response.headers.get("HX-Redirect") == "/BW/manage-internal-roles"

        # Follow the redirect to surface the flash on the next render.
        next_page = authenticated_owner_client.get("/BW/manage-internal-roles")
        assert next_page.status_code == 200
        body = next_page.data.decode()
        assert "invitation-flash" in body
        assert "ghost@example.com" in body
        assert (
            "Aucun utilisateur" in body
            or "n&#39;est pas membre" in body
            or "inactif" in body
        )
