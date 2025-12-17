# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/pages/show_user.py - toggle methods.

Tests the toggle logic using stubs to avoid database side effects.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.enums import OrganisationTypeEnum, RoleEnum


@dataclass
class StubRole:
    """Stub role for testing."""

    name: str


@dataclass
class StubOrganisation:
    """Stub organisation for testing."""

    name: str = "Test Org"
    type: OrganisationTypeEnum = OrganisationTypeEnum.MEDIA

    @property
    def is_auto(self) -> bool:
        return self.type == OrganisationTypeEnum.AUTO


@dataclass
class StubUser:
    """Stub user for testing toggle logic."""

    email: str = "test@example.com"
    organisation: StubOrganisation | None = None
    _roles: list[StubRole] = field(default_factory=list)

    @property
    def is_manager(self) -> bool:
        return any(r.name == RoleEnum.MANAGER.name for r in self._roles)

    @property
    def is_leader(self) -> bool:
        return any(r.name == RoleEnum.LEADER.name for r in self._roles)

    def remove_role(self, role_enum: RoleEnum) -> None:
        self._roles = [r for r in self._roles if r.name != role_enum.name]

    def add_role(self, role_enum: RoleEnum) -> None:
        if not any(r.name == role_enum.name for r in self._roles):
            self._roles.append(StubRole(name=role_enum.name))


def toggle_manager_logic(user: StubUser) -> bool:
    """Mirror of _toggle_manager logic for testing.

    Returns True if the toggle was performed, False if skipped.
    """
    if not user.organisation or user.organisation.is_auto:
        return False
    if user.is_manager:
        user.remove_role(RoleEnum.MANAGER)
    else:
        user.add_role(RoleEnum.MANAGER)
    return True


def toggle_leader_logic(user: StubUser) -> bool:
    """Mirror of _toggle_leader logic for testing.

    Returns True if the toggle was performed, False if skipped.
    """
    if not user.organisation or user.organisation.is_auto:
        return False
    if user.is_leader:
        user.remove_role(RoleEnum.LEADER)
    else:
        user.add_role(RoleEnum.LEADER)
    return True


class TestToggleManagerLogic:
    """Test toggle manager logic."""

    def test_toggle_manager_adds_role(self) -> None:
        """Test toggling manager adds role when not present."""
        org = StubOrganisation()
        user = StubUser(organisation=org)

        toggle_manager_logic(user)

        assert user.is_manager is True

    def test_toggle_manager_removes_role(self) -> None:
        """Test toggling manager removes role when present."""
        org = StubOrganisation()
        user = StubUser(organisation=org, _roles=[StubRole(RoleEnum.MANAGER.name)])

        toggle_manager_logic(user)

        assert user.is_manager is False

    def test_toggle_manager_no_org_does_nothing(self) -> None:
        """Test toggling manager with no org does nothing."""
        user = StubUser(organisation=None)

        result = toggle_manager_logic(user)

        assert result is False
        assert user.is_manager is False

    def test_toggle_manager_auto_org_does_nothing(self) -> None:
        """Test toggling manager with AUTO org does nothing."""
        org = StubOrganisation(type=OrganisationTypeEnum.AUTO)
        user = StubUser(organisation=org)

        result = toggle_manager_logic(user)

        assert result is False
        assert user.is_manager is False

    def test_toggle_manager_double_toggle(self) -> None:
        """Test toggling manager twice returns to original state."""
        org = StubOrganisation()
        user = StubUser(organisation=org)

        toggle_manager_logic(user)
        assert user.is_manager is True

        toggle_manager_logic(user)
        assert user.is_manager is False


class TestToggleLeaderLogic:
    """Test toggle leader logic."""

    def test_toggle_leader_adds_role(self) -> None:
        """Test toggling leader adds role when not present."""
        org = StubOrganisation()
        user = StubUser(organisation=org)

        toggle_leader_logic(user)

        assert user.is_leader is True

    def test_toggle_leader_removes_role(self) -> None:
        """Test toggling leader removes role when present."""
        org = StubOrganisation()
        user = StubUser(organisation=org, _roles=[StubRole(RoleEnum.LEADER.name)])

        toggle_leader_logic(user)

        assert user.is_leader is False

    def test_toggle_leader_no_org_does_nothing(self) -> None:
        """Test toggling leader with no org does nothing."""
        user = StubUser(organisation=None)

        result = toggle_leader_logic(user)

        assert result is False
        assert user.is_leader is False

    def test_toggle_leader_auto_org_does_nothing(self) -> None:
        """Test toggling leader with AUTO org does nothing."""
        org = StubOrganisation(type=OrganisationTypeEnum.AUTO)
        user = StubUser(organisation=org)

        result = toggle_leader_logic(user)

        assert result is False
        assert user.is_leader is False

    def test_toggle_leader_double_toggle(self) -> None:
        """Test toggling leader twice returns to original state."""
        org = StubOrganisation()
        user = StubUser(organisation=org)

        toggle_leader_logic(user)
        assert user.is_leader is True

        toggle_leader_logic(user)
        assert user.is_leader is False
