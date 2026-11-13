# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`emitter_org_id_for`: whose name a new marketplace offer goes out in."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from werkzeug.exceptions import Forbidden

from app.enums import BWRoleType, BWStatus, InvitationStatus
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.biz.views._offers_common import emitter_org_id_for
from app.modules.bw.bw_activation.models import BusinessWall, RoleAssignment

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _org_with_bw(db_session: Session, owner_id: int) -> Organisation:
    org = Organisation(name=f"Client {uuid.uuid4().hex[:6]}")
    db_session.add(org)
    db_session.flush()
    bw = BusinessWall(
        bw_type="leaders_experts",
        status=BWStatus.ACTIVE.value,
        is_free=False,
        owner_id=owner_id,
        payer_id=owner_id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    org.bw_id = bw.id
    return org


@pytest.fixture
def pr_manager(db_session: Session) -> User:
    agency = Organisation(name=f"Agency {uuid.uuid4().hex[:6]}")
    user = User(email=f"pr-{uuid.uuid4().hex[:8]}@example.com", active=True)
    user.organisation = agency
    db_session.add_all([agency, user])
    db_session.flush()
    return user


def _select(db_session: Session, user: User, org: Organisation) -> None:
    user.selected_bw_id = org.bw_id
    db_session.flush()


def test_own_organisation_by_default(app: Flask, pr_manager: User) -> None:
    with app.test_request_context():
        assert emitter_org_id_for(pr_manager) == pr_manager.organisation_id


@pytest.mark.parametrize("has_role", [True, False])
def test_a_client_wall_needs_a_live_pr_role(
    app: Flask, db_session: Session, pr_manager: User, has_role: bool
) -> None:
    """Revoking the role deletes its assignment; the selection stays."""
    owner = User(email=f"owner-{uuid.uuid4().hex[:8]}@example.com", active=True)
    db_session.add(owner)
    db_session.flush()
    client = _org_with_bw(db_session, owner_id=owner.id)
    if has_role:
        db_session.add(
            RoleAssignment(
                business_wall_id=client.bw_id,
                user_id=pr_manager.id,
                role_type=BWRoleType.BWPRE.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )
    _select(db_session, pr_manager, client)

    with app.test_request_context():
        if has_role:
            assert emitter_org_id_for(pr_manager) == client.id
        else:
            with pytest.raises(Forbidden):
                emitter_org_id_for(pr_manager)
