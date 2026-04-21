# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for Com'room access helper — bugs #0082, #0098, #0100."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.modules.wip.pr_access import user_can_access_comroom

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"pra_{uuid.uuid4().hex[:8]}@example.com"


def _ensure_role(db_session: Session, role_enum: RoleEnum) -> Role:
    role = db_session.query(Role).filter_by(name=role_enum.name).first()
    if role is None:
        role = Role(name=role_enum.name, description=role_enum.value)
        db_session.add(role)
        db_session.flush()
    return role


def _user_with_role(db_session: Session, role_enum: RoleEnum | None) -> User:
    user = User(email=_email(), active=True)
    if role_enum is not None:
        user.roles.append(_ensure_role(db_session, role_enum))
    db_session.add(user)
    db_session.flush()
    return user


@pytest.mark.parametrize(
    "role",
    [
        RoleEnum.PRESS_RELATIONS,
        RoleEnum.EXPERT,
        RoleEnum.TRANSFORMER,
        RoleEnum.ACADEMIC,
    ],
)
def test_non_journalist_community_roles_grant_access(
    db_session: Session, role: RoleEnum
):
    """Every community role except PRESS_MEDIA grants Com'room access."""
    user = _user_with_role(db_session, role)
    assert user_can_access_comroom(user) is True


def test_press_media_denied(db_session: Session):
    """Journalists use Newsroom, not Com'room."""
    user = _user_with_role(db_session, RoleEnum.PRESS_MEDIA)
    assert user_can_access_comroom(user) is False


def test_no_role_denied(db_session: Session):
    user = _user_with_role(db_session, None)
    assert user_can_access_comroom(user) is False
