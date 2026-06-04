# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for the `/BW/select-bw/<bw_id>` POST route.

Bug #0166 (Erick, 2026-06-02) :

> Bravo, l'interface est bien présente. Il y a même un bouton
> "Sélectionner le BW". En revanche, en appuyant sur le bouton
> "Sélectionner le BW" de Fake-OSS A380, il ne se passe rien. Or
> il faudrait se retrouver sur le BW de Fake-OSS A380.

Alfred (PR Agency Manager, BWPRE on a client BW) clicks the
selector — the POST sets `user.selected_bw_id` but the handler
then redirected him back to the same selector page because his
PR-Manager role was not part of `MANAGEMENT_ROLES`. He saw no
visible change. Fix : redirect PR managers to /wip/comroom where
they can actually publish content for the chosen BW.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.bw.bw_activation.models import (
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from tests.c_e2e.conftest import make_authenticated_client
from tests.c_e2e.modules.bw.conftest import create_bw_test_data

if TYPE_CHECKING:
    from flask import Flask


def _accept_pr_role(fresh_db, pr_owner, media_bw, role_type: BWRoleType) -> None:
    """Give the PR-side user the requested role on the media's BW
    so the selector treats them as a legitimate manageable BW."""
    role = RoleAssignment(
        business_wall_id=media_bw.id,
        user_id=pr_owner.id,
        role_type=role_type.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
    )
    fresh_db.session.add(role)
    fresh_db.session.commit()


class TestSelectBwPostForPRManager:
    """#0166 part 2 — the « Sélectionner le BW » button must actually
    take the PR manager somewhere useful."""

    def test_pr_manager_external_lands_on_comroom_after_selecting(
        self, app: Flask, fresh_db
    ):
        """A PR Agency owner who picks a client BW must land on
        /wip/comroom (the publication tool they actually need),
        NOT back on /BW/select-bw (the previous broken behaviour)."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_pr_bw=True,
        )
        _accept_pr_role(fresh_db, data["pr_owner"], data["media_bw"], BWRoleType.BWPRE)

        client = make_authenticated_client(app, data["pr_owner"])
        response = client.post(
            f"/BW/select-bw/{data['media_bw'].id}",
            follow_redirects=False,
        )

        assert response.status_code == 302
        location = response.headers.get("Location", "")
        assert "/wip/comroom" in location, (
            "PR managers must land on /wip/comroom after selecting a "
            "client BW, not be sent back to /BW/select-bw (#0166)"
        )

    def test_pr_manager_internal_also_lands_on_comroom(
        self, app: Flask, fresh_db
    ):
        """Same target for BWPRi (internal PR manager) — both PR
        roles are publication-oriented, not BW-management."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_pr_bw=True,
        )
        _accept_pr_role(fresh_db, data["pr_owner"], data["media_bw"], BWRoleType.BWPRI)

        client = make_authenticated_client(app, data["pr_owner"])
        response = client.post(
            f"/BW/select-bw/{data['media_bw'].id}",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/wip/comroom" in response.headers.get("Location", "")

    def test_selection_persists_user_selected_bw_id(
        self, app: Flask, fresh_db
    ):
        """The selected_bw_id column must record the choice
        regardless of which destination page the user is routed to."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_pr_bw=True,
        )
        _accept_pr_role(fresh_db, data["pr_owner"], data["media_bw"], BWRoleType.BWPRE)

        client = make_authenticated_client(app, data["pr_owner"])
        client.post(
            f"/BW/select-bw/{data['media_bw'].id}",
            follow_redirects=False,
        )

        fresh_db.session.refresh(data["pr_owner"])
        assert data["pr_owner"].selected_bw_id == data["media_bw"].id

    def test_bw_owner_still_lands_on_dashboard(self, app: Flask, fresh_db):
        """Back-compat : a BW owner / BWMi / BWMe keeps landing on
        /BW/dashboard (the existing management UI)."""
        data = create_bw_test_data(
            fresh_db,
            create_pr_user=True,
            create_pr_bw=True,
        )
        # media_owner manages their own BW.
        client = make_authenticated_client(app, data["media_owner"])
        response = client.post(
            f"/BW/select-bw/{data['media_bw'].id}",
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert "/BW/dashboard" in response.headers.get("Location", "")
