# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Who appears in « Membres actuels » on the B03 page.

Tickets #0259, #0260, #0261 and #0265 are four reports of the same
screen: the list did not match reality. A PR agency head (external) was
shown as an internal member, the BWMi and BWPRi who had accepted were
missing, and the owner's own presence was in doubt. All four were closed
without a test on the rendered page, so this file pins the four rules
the list follows.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.models.auth import User
from app.modules.bw.bw_activation.models import (
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.modules.bw.bw_activation.models import BusinessWall

MEMBERS_URL = "/BW/manage-organisation-members"


def add_member(
    db_session: Session,
    bw: BusinessWall,
    role_type: BWRoleType,
    invitation_status: InvitationStatus,
    last_name: str,
) -> User:
    """Create a user holding `role_type` on `bw` and return them."""
    user = User(
        email=f"{last_name.lower()}_{uuid.uuid4().hex[:6]}@example.com",
        first_name="Test",
        last_name=last_name,
        active=True,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(
        RoleAssignment(
            business_wall_id=bw.id,
            user_id=user.id,
            role_type=role_type.value,
            invitation_status=invitation_status.value,
        )
    )
    db_session.flush()
    return user


class TestCurrentMembersList:
    def test_accepted_internal_roles_are_listed(
        self,
        db_session: Session,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
    ) -> None:
        """Bugs #0260 / #0265 : « Rick Jenkins ne figure toujours pas dans
        la liste des membres » alors qu'il avait accepté son rôle."""
        bwmi = add_member(
            db_session,
            test_business_wall,
            BWRoleType.BWMI,
            InvitationStatus.ACCEPTED,
            "Castades",
        )
        bwpri = add_member(
            db_session,
            test_business_wall,
            BWRoleType.BWPRI,
            InvitationStatus.ACCEPTED,
            "Jenkins",
        )

        body = authenticated_owner_client.get(MEMBERS_URL).data.decode()

        assert bwmi.email in body
        assert bwpri.email in body

    def test_pending_role_invitation_is_not_a_member_yet(
        self,
        db_session: Session,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
    ) -> None:
        """An invitation that has not been accepted is not a membership.

        The counterpart of #0260 : the list must not run ahead of the
        invitee's answer, otherwise « Membres actuels » counts people who
        never joined.
        """
        invited = add_member(
            db_session,
            test_business_wall,
            BWRoleType.BWMI,
            InvitationStatus.PENDING,
            "Thauron",
        )

        body = authenticated_owner_client.get(MEMBERS_URL).data.decode()

        assert invited.email not in body

    def test_external_pr_manager_is_not_listed(
        self,
        db_session: Session,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
    ) -> None:
        """Bug #0259 : « La PR Agency ne devrait pas apparaître dans la
        liste des membres internes ». The external partner's head accepted
        a BWPRe role, which is a partnership, not a membership."""
        external = add_member(
            db_session,
            test_business_wall,
            BWRoleType.BWPRE,
            InvitationStatus.ACCEPTED,
            "Capri",
        )

        body = authenticated_owner_client.get(MEMBERS_URL).data.decode()

        assert external.email not in body

    def test_owner_is_always_listed(
        self,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
        test_user_owner: User,
    ) -> None:
        """Bug #0261 : « Une dirigeante qui initie le BW n'en est pas Owner
        pour autant ». The owner is a member by construction — the list is
        also the only place they can check it."""
        body = authenticated_owner_client.get(MEMBERS_URL).data.decode()

        assert test_user_owner.email in body


class TestRoleSwap:
    """Bugs #0259 / #0260 : the two colleagues had been invited to each
    other's role, and swapping them left one of them role-less.
    """

    def test_swapping_two_internal_roles_keeps_both_members(
        self,
        db_session: Session,
        authenticated_owner_client: FlaskClient,
        test_business_wall: BusinessWall,
    ) -> None:
        jenkins = add_member(
            db_session,
            test_business_wall,
            BWRoleType.BWMI,
            InvitationStatus.ACCEPTED,
            "Jenkins",
        )
        castades = add_member(
            db_session,
            test_business_wall,
            BWRoleType.BWPRI,
            InvitationStatus.ACCEPTED,
            "Castades",
        )

        # « J'ai donc retiré chacun de son rôle erroné pour réattribuer
        # chacun à la bonne place. »
        for user, new_role in (
            (jenkins, BWRoleType.BWPRI),
            (castades, BWRoleType.BWMI),
        ):
            assignment = (
                db_session.query(RoleAssignment)
                .filter_by(business_wall_id=test_business_wall.id, user_id=user.id)
                .one()
            )
            assignment.role_type = new_role.value
        db_session.flush()

        body = authenticated_owner_client.get(MEMBERS_URL).data.decode()

        assert jenkins.email in body
        assert castades.email in body
