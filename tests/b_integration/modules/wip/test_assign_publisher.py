# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`assign_publisher` attributes a Commande or an Avis d'enquête to the
organisation the user acts for, and refuses one they may not publish for."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import User
from app.models.errors import BusinessRuleError
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    BWStatus,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.wip.crud.cbvs._base import assign_publisher

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _mk_user_org_bw(db_session: Session, name: str) -> tuple[User, BusinessWall]:
    """A user, their organisation and its active Business Wall."""
    unique = uuid.uuid4().hex[:8]
    org = Organisation(name=f"{name} {unique}")
    db_session.add(org)
    db_session.flush()
    user = User(email=f"{name.lower()}-{unique}@example.com", active=True)
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    org.bw_id = bw.id
    db_session.flush()
    return user, bw


def _assign(app: Flask, user: User, publisher_id: int | None = None) -> int | None:
    model = SimpleNamespace(publisher_id=publisher_id)
    with app.test_request_context():
        g.user = user
        assign_publisher(model)
    return model.publisher_id


class TestAssignPublisher:
    def test_defaults_to_own_organisation(self, app: Flask, db_session: Session):
        user, _ = _mk_user_org_bw(db_session, "Self")

        assert _assign(app, user) == user.organisation_id

    def test_uses_a_managed_business_wall(self, app: Flask, db_session: Session):
        user, _ = _mk_user_org_bw(db_session, "Manager")
        _, client_bw = _mk_user_org_bw(db_session, "Client")
        db_session.add(
            RoleAssignment(
                business_wall_id=client_bw.id,
                user_id=user.id,
                role_type=BWRoleType.BWPRI.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )
        user.selected_bw_id = client_bw.id
        db_session.flush()

        assert _assign(app, user) == client_bw.organisation_id

    def test_refuses_a_stale_selected_business_wall(
        self, app: Flask, db_session: Session
    ):
        """The user once managed this Business Wall and no longer does."""
        user, _ = _mk_user_org_bw(db_session, "Former")
        _, stranger_bw = _mk_user_org_bw(db_session, "Stranger")
        user.selected_bw_id = stranger_bw.id
        db_session.flush()

        with pytest.raises(BusinessRuleError):
            _assign(app, user)

    def test_keeps_an_existing_attribution(self, app: Flask, db_session: Session):
        user, _ = _mk_user_org_bw(db_session, "Editor")
        _, other_bw = _mk_user_org_bw(db_session, "Other")

        assert _assign(app, user, other_bw.organisation_id) == (
            other_bw.organisation_id
        )
