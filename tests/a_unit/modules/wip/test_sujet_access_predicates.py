# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for app.modules.wip.sujet_access."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

import pytest

from app.enums import BWType, RoleEnum
from app.modules.wip.sujet_access import user_can_access_sujets

if TYPE_CHECKING:
    from app.models.auth import User


class _User:
    """Minimal ``User`` stand-in matching the sujet_access usage surface."""

    def __init__(
        self,
        *,
        user_id: int = 1,
        roles: Iterable[object] = (),
        is_anonymous: bool = False,
    ) -> None:
        self.id = user_id
        self._roles = {self._key(r) for r in roles}
        self.is_anonymous = is_anonymous

    @staticmethod
    def _key(role: object) -> str:
        if isinstance(role, RoleEnum):
            return role.name
        if hasattr(role, "name"):
            return str(role.name)
        return str(role)

    def has_role(self, role: object) -> bool:
        return self._key(role) in self._roles


def _user(
    *,
    user_id: int = 1,
    roles: Iterable[object] = (),
    is_anonymous: bool = False,
) -> User:
    return cast("User", _User(user_id=user_id, roles=roles, is_anonymous=is_anonymous))


class _BusinessWall:
    def __init__(self, *, bw_type: str = BWType.MEDIA.value) -> None:
        self.bw_type = bw_type


def _loader(bw: _BusinessWall | None):
    def _load(_user: object) -> _BusinessWall | None:
        return bw

    return _load


_NO_BW = _loader(None)


# ---------------------------------------------------------------------------
# user_can_access_sujets tests
# ---------------------------------------------------------------------------


class TestUserCanAccessSujets:
    def test_anonymous_denied(self) -> None:
        assert user_can_access_sujets(_user(is_anonymous=True)) is False

    def test_none_user_denied(self) -> None:
        assert user_can_access_sujets(None) is False  # type: ignore[arg-type]

    def test_no_bw_denied_even_with_press_media(self) -> None:
        user = _user(roles=[RoleEnum.PRESS_MEDIA])
        assert user_can_access_sujets(user, bw_loader=_NO_BW) is False

    @pytest.mark.parametrize(
        "bw_type",
        [
            BWType.PR.value,
            BWType.TRANSFORMERS.value,
            BWType.LEADERS_EXPERTS.value,
        ],
    )
    def test_non_media_bw_denied(self, bw_type: str) -> None:
        user = _user(roles=[RoleEnum.PRESS_MEDIA])
        bw = _BusinessWall(bw_type=bw_type)
        assert user_can_access_sujets(user, bw_loader=_loader(bw)) is False

    @pytest.mark.parametrize(
        "role",
        [
            RoleEnum.ACADEMIC,
            RoleEnum.EXPERT,
            RoleEnum.PRESS_RELATIONS,
            RoleEnum.TRANSFORMER,
        ],
    )
    def test_media_bw_without_press_media_role_denied(self, role: RoleEnum) -> None:
        user = _user(roles=[role])
        bw = _BusinessWall(bw_type=BWType.MEDIA.value)
        assert user_can_access_sujets(user, bw_loader=_loader(bw)) is False

    def test_media_bw_with_no_role_denied(self) -> None:
        user = _user()
        bw = _BusinessWall(bw_type=BWType.MEDIA.value)
        assert user_can_access_sujets(user, bw_loader=_loader(bw)) is False

    @pytest.mark.parametrize(
        "bw_type",
        [
            BWType.MEDIA.value,
            BWType.MICRO.value,
            BWType.NEWS_AGENCY.value,
        ],
    )
    def test_media_bw_with_press_media_role_allowed(self, bw_type: str) -> None:
        user = _user(roles=[RoleEnum.PRESS_MEDIA])
        bw = _BusinessWall(bw_type=bw_type)
        assert user_can_access_sujets(user, bw_loader=_loader(bw)) is True
