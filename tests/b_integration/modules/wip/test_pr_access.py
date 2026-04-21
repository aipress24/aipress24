# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for Com'room access helper — bugs #0098 and #0100."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.modules.wip.pr_access import user_can_access_comroom

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _email() -> str:
    return f"pra_{uuid.uuid4().hex[:8]}@example.com"


def _user_with_profile(db_session: Session, profile_code: str | None) -> User:
    user = User(email=_email(), active=True)
    if profile_code is not None:
        profile = KYCProfile()
        profile.profile_code = profile_code
        user.profile = profile
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def press_relations_role(db_session: Session) -> Role:
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_RELATIONS.name).first()
    if role is None:
        role = Role(
            name=RoleEnum.PRESS_RELATIONS.name,
            description=RoleEnum.PRESS_RELATIONS.value,
        )
        db_session.add(role)
        db_session.flush()
    return role


def test_press_relations_role_grants_access(
    db_session: Session, press_relations_role: Role
):
    user = _user_with_profile(db_session, None)
    user.roles.append(press_relations_role)
    db_session.flush()
    assert user_can_access_comroom(user) is True


def test_xp_pr_profile_grants_access(db_session: Session):
    user = _user_with_profile(db_session, "XP_PR")
    assert user_can_access_comroom(user) is True


def test_tr_cs_org_pr_profile_grants_access(db_session: Session):
    user = _user_with_profile(db_session, "TR_CS_ORG_PR")
    assert user_can_access_comroom(user) is True


def test_transformer_without_pr_denied(db_session: Session):
    user = _user_with_profile(db_session, "TR_CS_ORG")
    assert user_can_access_comroom(user) is False


def test_expert_without_pr_denied(db_session: Session):
    user = _user_with_profile(db_session, "XP_ANY")
    assert user_can_access_comroom(user) is False


def test_no_profile_denied(db_session: Session):
    user = _user_with_profile(db_session, None)
    assert user_can_access_comroom(user) is False


def test_unknown_profile_code_denied(db_session: Session):
    user = _user_with_profile(db_session, "NOT_A_REAL_PROFILE")
    assert user_can_access_comroom(user) is False
