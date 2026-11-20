# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests extending PR agency partnership rights to all agency members."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.enums import BWRoleType, BWStatus, BWType, InvitationStatus, RoleEnum
from app.flask.extensions import db
from app.models.auth import Role, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    Partnership,
    PartnershipStatus,
    PermissionType,
    RoleAssignment,
)
from app.modules.bw.bw_activation.user_utils import (
    can_user_publish_for,
    get_user_rights_on_bw,
    user_has_pr_partnership_on_bw,
)
from app.modules.wip.crud.cbvs.events import _has_events_mission_on
from app.modules.wip.pr_access import (
    user_has_mission,
    user_is_acting_as_pr_manager,
)


def _setup_partnership_with_agency_member():
    suffix = uuid4().hex[:8]
    pr_role = db.session.scalar(
        select(Role).where(Role.name == RoleEnum.PRESS_RELATIONS.name)
    )
    if pr_role is None:
        pr_role = Role(name=RoleEnum.PRESS_RELATIONS.name)
        db.session.add(pr_role)
        db.session.flush()

    # Client organisation + BW
    client_owner = User(
        email=f"client-owner-{suffix}@example.com",
        first_name="Client",
        last_name="Owner",
        active=True,
    )
    db.session.add(client_owner)
    db.session.flush()

    client_org = Organisation(name=f"Client Org {suffix}")
    db.session.add(client_org)
    db.session.flush()
    client_owner.organisation_id = client_org.id

    client_bw = BusinessWall(
        bw_type=BWType.LEADERS_EXPERTS.value,
        status=BWStatus.ACTIVE.value,
        name=f"Client BW {suffix}",
        owner_id=client_owner.id,
        payer_id=client_owner.id,
        organisation_id=client_org.id,
        missions={"press_release": True, "events": True, "missions": False},
    )
    db.session.add(client_bw)
    db.session.flush()
    client_org.bw_id = client_bw.id
    client_org.bw_active = client_bw.bw_type

    # PR Agency organisation + BW + owner + another member
    agency_owner = User(
        email=f"agency-owner-{suffix}@example.com",
        first_name="Agency",
        last_name="Owner",
        active=True,
        roles=[pr_role],
    )
    agency_member = User(
        email=f"agency-member-{suffix}@example.com",
        first_name="Agency",
        last_name="Member",
        active=True,
        roles=[pr_role],
    )
    db.session.add_all([agency_owner, agency_member])
    db.session.flush()

    agency_org = Organisation(name=f"PR Agency {suffix}")
    db.session.add(agency_org)
    db.session.flush()
    agency_owner.organisation_id = agency_org.id
    agency_member.organisation_id = agency_org.id

    agency_bw = BusinessWall(
        bw_type=BWType.PR.value,
        status=BWStatus.ACTIVE.value,
        name=f"Agency BW {suffix}",
        owner_id=agency_owner.id,
        payer_id=agency_owner.id,
        organisation_id=agency_org.id,
    )
    db.session.add(agency_bw)
    db.session.flush()
    agency_org.bw_id = agency_bw.id
    agency_org.bw_active = agency_bw.bw_type

    # Active Partnership + RoleAssignment on agency_owner (not agency_member)
    partnership = Partnership(
        business_wall_id=client_bw.id,
        partner_bw_id=str(agency_bw.id),
        status=PartnershipStatus.ACTIVE.value,
        invited_by_user_id=client_owner.id,
    )
    owner_assignment = RoleAssignment(
        business_wall_id=client_bw.id,
        user_id=agency_owner.id,
        role_type=BWRoleType.BWPRE.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
    )
    db.session.add_all([partnership, owner_assignment])
    db.session.commit()

    return client_org, client_bw, agency_member


def test_pr_agency_member_inherits_partnership_publication_rights(app, client) -> None:
    """Any member of a PR agency with active Partnership can select
    the client BW and publish press releases / events per `bw.missions`.
    """
    with app.app_context():
        client_org, client_bw, member = _setup_partnership_with_agency_member()
        client_bw_id = client_bw.id
        client_org_id = client_org.id
        member_id = member.id
        member_fs_uniquifier = member.fs_uniquifier

        assert user_has_pr_partnership_on_bw(member, client_bw) is True
        rights = get_user_rights_on_bw(member, client_bw)
        assert any("communiqués de presse" in r for r in rights)
        assert any("événements" in r for r in rights)
        assert can_user_publish_for(member, client_org_id) is True
        assert _has_events_mission_on(member, client_org) is True

    with client.session_transaction() as sess:
        sess["_user_id"] = member_fs_uniquifier

    resp = client.post(f"/BW/select-bw/{client_bw_id}", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/wip/comroom")

    with app.app_context():
        refreshed_member = db.session.get(User, member_id)
        assert refreshed_member is not None
        assert refreshed_member.selected_bw_id == client_bw_id
        assert user_is_acting_as_pr_manager(refreshed_member) is True
        assert user_has_mission(refreshed_member, PermissionType.PRESS_RELEASE) is True
        assert user_has_mission(refreshed_member, PermissionType.EVENTS) is True
        assert user_has_mission(refreshed_member, PermissionType.MISSIONS) is False
