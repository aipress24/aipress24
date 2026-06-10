# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for ``app.modules.wip.pr_access``.

The ``pr_access`` module gates access to WIP rooms (Com'room, Newsroom,
Eventroom) and to PR-manager *missions* on a Business Wall. Its predicates
combine two collaborators:

* ``user.has_role(...)`` -- delegated through ``app.services.roles.has_role``;
* ``get_selected_business_wall_for_user(user)`` -- DB + session I/O.

Both collaborators are now injectable so we can verify the predicates with
plain stand-in objects -- no mocking library and no fixture-level patching.
Each test pins one row of the predicate's truth table and asserts the
tangible return value (or the ``Forbidden`` exception for ``check_mission``).
"""

from __future__ import annotations

from collections.abc import Iterable

import pytest
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.modules.bw.bw_activation.models import (
    BWRoleType,
    InvitationStatus,
    PermissionType,
)
from app.modules.wip.pr_access import (
    COMROOM_COMMUNITY_ROLES,
    EVENTROOM_COMMUNITY_ROLES,
    check_mission,
    user_can_access_comroom,
    user_can_access_eventroom,
    user_can_access_newsroom,
    user_has_mission,
    user_is_acting_as_pr_manager,
)

# ---------------------------------------------------------------------------
# Stand-in collaborators (plain duck-typed classes -- no mocking library).
# ---------------------------------------------------------------------------


class _User:
    """Minimal ``User`` stand-in matching the pr_access usage surface."""

    def __init__(
        self,
        *,
        user_id: int = 1,
        roles: Iterable[object] = (),
        is_anonymous: bool = False,
        is_managing_another_bw: bool = False,
    ) -> None:
        self.id = user_id
        self._roles = {self._key(r) for r in roles}
        self.is_anonymous = is_anonymous
        self.is_managing_another_bw = is_managing_another_bw

    @staticmethod
    def _key(role: object) -> str:
        if isinstance(role, RoleEnum):
            return role.name
        if hasattr(role, "name"):
            return str(role.name)
        return str(role)

    def has_role(self, role: object) -> bool:
        return self._key(role) in self._roles


class _Permission:
    def __init__(self, kind: str, *, is_granted: bool = True) -> None:
        self.permission_type = kind
        self.is_granted = is_granted


class _Assignment:
    def __init__(
        self,
        *,
        user_id: int,
        role_type: str,
        invitation_status: str = InvitationStatus.ACCEPTED.value,
        permissions: Iterable[_Permission] = (),
    ) -> None:
        self.user_id = user_id
        self.role_type = role_type
        self.invitation_status = invitation_status
        self.permissions = list(permissions)


class _BusinessWall:
    def __init__(
        self,
        *,
        owner_id: int = 999,
        role_assignments: Iterable[_Assignment] = (),
    ) -> None:
        self.owner_id = owner_id
        self.role_assignments = list(role_assignments)


def _loader(bw: _BusinessWall | None):
    """Return a ``bw_loader`` callable yielding ``bw`` regardless of input."""

    def _load(_user: object) -> _BusinessWall | None:
        return bw

    return _load


_NO_BW = _loader(None)


def _bw_with_role(
    user_id: int,
    role_type: str,
    *,
    owner_id: int = 999,
    invitation_status: str = InvitationStatus.ACCEPTED.value,
    granted_missions: Iterable[PermissionType] = (),
    denied_missions: Iterable[PermissionType] = (),
) -> _BusinessWall:
    """Build a BW that contains one assignment for ``user_id``."""
    perms = [_Permission(m.value, is_granted=True) for m in granted_missions]
    perms += [_Permission(m.value, is_granted=False) for m in denied_missions]
    return _BusinessWall(
        owner_id=owner_id,
        role_assignments=[
            _Assignment(
                user_id=user_id,
                role_type=role_type,
                invitation_status=invitation_status,
                permissions=perms,
            )
        ],
    )


# ---------------------------------------------------------------------------
# Canonical role frozensets.
# ---------------------------------------------------------------------------


class TestCanonicalRoleSets:
    def test_comroom_excludes_press_media(self) -> None:
        assert RoleEnum.PRESS_MEDIA not in COMROOM_COMMUNITY_ROLES
        expected = frozenset(
            {
                RoleEnum.ACADEMIC,
                RoleEnum.EXPERT,
                RoleEnum.PRESS_RELATIONS,
                RoleEnum.TRANSFORMER,
            }
        )
        assert expected == COMROOM_COMMUNITY_ROLES

    def test_eventroom_includes_press_media(self) -> None:
        assert RoleEnum.PRESS_MEDIA in EVENTROOM_COMMUNITY_ROLES
        expected = COMROOM_COMMUNITY_ROLES | {RoleEnum.PRESS_MEDIA}
        assert expected == EVENTROOM_COMMUNITY_ROLES

    def test_frozensets_are_immutable(self) -> None:
        assert isinstance(COMROOM_COMMUNITY_ROLES, frozenset)
        assert isinstance(EVENTROOM_COMMUNITY_ROLES, frozenset)


# ---------------------------------------------------------------------------
# user_can_access_newsroom -- pure role check, no BW lookup.
# ---------------------------------------------------------------------------


class TestUserCanAccessNewsroom:
    def test_anonymous_denied(self) -> None:
        assert user_can_access_newsroom(_User(is_anonymous=True)) is False

    def test_none_user_denied(self) -> None:
        assert user_can_access_newsroom(None) is False  # type: ignore[arg-type]

    def test_press_media_allowed(self) -> None:
        assert user_can_access_newsroom(_User(roles=[RoleEnum.PRESS_MEDIA])) is True

    @pytest.mark.parametrize(
        "role",
        [
            RoleEnum.ACADEMIC,
            RoleEnum.EXPERT,
            RoleEnum.PRESS_RELATIONS,
            RoleEnum.TRANSFORMER,
        ],
    )
    def test_non_journalists_denied(self, role: RoleEnum) -> None:
        assert user_can_access_newsroom(_User(roles=[role])) is False

    def test_no_roles_denied(self) -> None:
        assert user_can_access_newsroom(_User()) is False


# ---------------------------------------------------------------------------
# user_can_access_comroom -- community roles OR acting as PR manager.
# ---------------------------------------------------------------------------


class TestUserCanAccessComroom:
    def test_anonymous_denied(self) -> None:
        assert user_can_access_comroom(_User(is_anonymous=True)) is False

    def test_none_user_denied(self) -> None:
        assert user_can_access_comroom(None) is False  # type: ignore[arg-type]

    @pytest.mark.parametrize("role", sorted(COMROOM_COMMUNITY_ROLES, key=str))
    def test_each_community_role_grants_access(self, role: RoleEnum) -> None:
        user = _User(roles=[role])
        assert user_can_access_comroom(user, bw_loader=_NO_BW) is True

    def test_press_media_alone_denied(self) -> None:
        user = _User(roles=[RoleEnum.PRESS_MEDIA])
        assert user_can_access_comroom(user, bw_loader=_NO_BW) is False

    def test_pr_manager_fallback_allowed(self) -> None:
        user = _User(user_id=42, is_managing_another_bw=True)
        bw = _bw_with_role(42, BWRoleType.BWPRE.value)
        assert user_can_access_comroom(user, bw_loader=_loader(bw)) is True

    def test_no_role_no_pr_denied(self) -> None:
        user = _User(user_id=42, is_managing_another_bw=False)
        assert user_can_access_comroom(user, bw_loader=_NO_BW) is False


# ---------------------------------------------------------------------------
# user_can_access_eventroom -- mirrors comroom but PRESS_MEDIA is included.
# ---------------------------------------------------------------------------


class TestUserCanAccessEventroom:
    def test_anonymous_denied(self) -> None:
        assert user_can_access_eventroom(_User(is_anonymous=True)) is False

    def test_none_user_denied(self) -> None:
        assert user_can_access_eventroom(None) is False  # type: ignore[arg-type]

    @pytest.mark.parametrize("role", sorted(EVENTROOM_COMMUNITY_ROLES, key=str))
    def test_each_eventroom_role_grants_access(self, role: RoleEnum) -> None:
        user = _User(roles=[role])
        assert user_can_access_eventroom(user, bw_loader=_NO_BW) is True

    def test_pr_manager_fallback_allowed(self) -> None:
        user = _User(user_id=7, is_managing_another_bw=True)
        bw = _bw_with_role(7, BWRoleType.BWPRI.value)
        assert user_can_access_eventroom(user, bw_loader=_loader(bw)) is True

    def test_no_role_no_pr_denied(self) -> None:
        user = _User(user_id=7)
        assert user_can_access_eventroom(user, bw_loader=_NO_BW) is False


# ---------------------------------------------------------------------------
# user_is_acting_as_pr_manager -- multi-input truth table pin.
# ---------------------------------------------------------------------------


class TestUserIsActingAsPrManager:
    def test_anonymous_denied(self) -> None:
        assert user_is_acting_as_pr_manager(_User(is_anonymous=True)) is False

    def test_none_user_denied(self) -> None:
        assert user_is_acting_as_pr_manager(None) is False  # type: ignore[arg-type]

    def test_not_managing_another_bw_denied(self) -> None:
        user = _User(user_id=1, is_managing_another_bw=False)
        assert user_is_acting_as_pr_manager(user, bw_loader=_NO_BW) is False

    def test_no_bw_loaded_denied(self) -> None:
        user = _User(user_id=1, is_managing_another_bw=True)
        assert user_is_acting_as_pr_manager(user, bw_loader=_NO_BW) is False

    @pytest.mark.parametrize(
        "role_type",
        [BWRoleType.BWPRI.value, BWRoleType.BWPRE.value],
    )
    def test_accepted_pr_role_grants(self, role_type: str) -> None:
        user = _User(user_id=42, is_managing_another_bw=True)
        bw = _bw_with_role(42, role_type)
        assert user_is_acting_as_pr_manager(user, bw_loader=_loader(bw)) is True

    def test_pending_invitation_denied(self) -> None:
        user = _User(user_id=42, is_managing_another_bw=True)
        bw = _bw_with_role(
            42,
            BWRoleType.BWPRE.value,
            invitation_status=InvitationStatus.PENDING.value,
        )
        assert user_is_acting_as_pr_manager(user, bw_loader=_loader(bw)) is False

    def test_non_pr_role_denied(self) -> None:
        user = _User(user_id=42, is_managing_another_bw=True)
        bw = _bw_with_role(42, BWRoleType.BWMI.value)
        assert user_is_acting_as_pr_manager(user, bw_loader=_loader(bw)) is False

    def test_assignment_for_different_user_denied(self) -> None:
        user = _User(user_id=42, is_managing_another_bw=True)
        bw = _bw_with_role(99, BWRoleType.BWPRE.value)
        assert user_is_acting_as_pr_manager(user, bw_loader=_loader(bw)) is False


# ---------------------------------------------------------------------------
# user_has_mission -- owner shortcut + per-assignment permission lookup.
# ---------------------------------------------------------------------------


class TestUserHasMission:
    def test_anonymous_denied(self) -> None:
        anon = _User(is_anonymous=True)
        assert user_has_mission(anon, PermissionType.EVENTS) is False

    def test_none_user_denied(self) -> None:
        assert (
            user_has_mission(None, PermissionType.EVENTS)  # type: ignore[arg-type]
            is False
        )

    def test_no_bw_denied(self) -> None:
        user = _User(user_id=1)
        assert user_has_mission(user, PermissionType.EVENTS, bw_loader=_NO_BW) is False

    def test_owner_has_every_mission(self) -> None:
        user = _User(user_id=42)
        bw = _BusinessWall(owner_id=42)  # no assignments needed
        loader = _loader(bw)
        for mission in PermissionType:
            assert user_has_mission(user, mission, bw_loader=loader) is True

    def test_granted_permission_allowed(self) -> None:
        user = _User(user_id=7)
        bw = _bw_with_role(
            7, BWRoleType.BWPRE.value, granted_missions=[PermissionType.EVENTS]
        )
        assert (
            user_has_mission(user, PermissionType.EVENTS, bw_loader=_loader(bw)) is True
        )

    def test_ungranted_permission_denied(self) -> None:
        user = _User(user_id=7)
        bw = _bw_with_role(
            7, BWRoleType.BWPRE.value, denied_missions=[PermissionType.EVENTS]
        )
        assert (
            user_has_mission(user, PermissionType.EVENTS, bw_loader=_loader(bw))
            is False
        )

    def test_mission_for_other_user_denied(self) -> None:
        user = _User(user_id=7)
        bw = _bw_with_role(
            8,  # assignment belongs to a different user
            BWRoleType.BWPRE.value,
            granted_missions=[PermissionType.EVENTS],
        )
        assert (
            user_has_mission(user, PermissionType.EVENTS, bw_loader=_loader(bw))
            is False
        )

    def test_pending_assignment_denied(self) -> None:
        user = _User(user_id=7)
        bw = _bw_with_role(
            7,
            BWRoleType.BWPRE.value,
            invitation_status=InvitationStatus.PENDING.value,
            granted_missions=[PermissionType.EVENTS],
        )
        assert (
            user_has_mission(user, PermissionType.EVENTS, bw_loader=_loader(bw))
            is False
        )

    def test_wrong_mission_denied(self) -> None:
        # Granted EVENTS permission does not grant MISSIONS.
        user = _User(user_id=7)
        bw = _bw_with_role(
            7, BWRoleType.BWPRE.value, granted_missions=[PermissionType.EVENTS]
        )
        assert (
            user_has_mission(user, PermissionType.MISSIONS, bw_loader=_loader(bw))
            is False
        )


# ---------------------------------------------------------------------------
# check_mission -- both branches of the guard.
# ---------------------------------------------------------------------------


class TestCheckMission:
    def test_non_pr_manager_returns_none(self) -> None:
        # Not acting as PR manager => the guard does nothing.
        user = _User(user_id=1, is_managing_another_bw=False)
        result = check_mission(user, PermissionType.EVENTS, bw_loader=_NO_BW)
        assert result is None

    def test_pr_manager_with_mission_returns_none(self) -> None:
        user = _User(user_id=7, is_managing_another_bw=True)
        bw = _bw_with_role(
            7, BWRoleType.BWPRE.value, granted_missions=[PermissionType.EVENTS]
        )
        result = check_mission(user, PermissionType.EVENTS, bw_loader=_loader(bw))
        assert result is None

    def test_pr_manager_without_mission_raises_forbidden(self) -> None:
        user = _User(user_id=7, is_managing_another_bw=True)
        bw = _bw_with_role(
            7, BWRoleType.BWPRE.value, denied_missions=[PermissionType.EVENTS]
        )
        with pytest.raises(Forbidden):
            check_mission(user, PermissionType.EVENTS, bw_loader=_loader(bw))

    def test_pr_manager_owner_passes(self) -> None:
        # User happens to be both BW owner and acting PR manager; owner
        # shortcut in user_has_mission means the guard returns None.
        user = _User(user_id=42, is_managing_another_bw=True)
        bw = _BusinessWall(
            owner_id=42,
            role_assignments=[
                _Assignment(user_id=42, role_type=BWRoleType.BWPRE.value)
            ],
        )
        result = check_mission(user, PermissionType.EVENTS, bw_loader=_loader(bw))
        assert result is None
