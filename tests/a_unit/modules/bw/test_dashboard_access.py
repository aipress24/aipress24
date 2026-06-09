# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `can_access_bw_dashboard` and the
`DASHBOARD_ACCESS_ROLES` frozenset in
`app.modules.bw.bw_activation.utils`.

This is the BW management-dashboard gate. The route guard
(`/bw/dashboard`) and the « confirm role invitation » flow both
consult this single source of truth — drift between them would
let either :
- a confirmed BWPRi user reach a dashboard they don't belong in
- a legitimate BWMI user get a 403 on the dashboard they own

Bug #0157 specifically narrowed the role list to exclude BWPRi/BWPRe
(external PR managers) — pin so a future « add BWPRi back » without
updating the related tests gets caught.
"""

from __future__ import annotations

from app.modules.bw.bw_activation.models import BWRoleType
from app.modules.bw.bw_activation.utils import (
    DASHBOARD_ACCESS_ROLES,
    can_access_bw_dashboard,
)


class TestDashboardAccessRoles:
    def test_is_frozenset(self):
        """The constant is a frozenset so it can't be mutated by
        code that imports it. Pin so a future refactor to a plain
        set doesn't open up runtime mutation."""
        assert isinstance(DASHBOARD_ACCESS_ROLES, frozenset)

    def test_contains_bw_owner(self):
        """The BW owner always has dashboard access — the role
        was created precisely for that purpose."""
        assert BWRoleType.BW_OWNER.value in DASHBOARD_ACCESS_ROLES

    def test_contains_internal_pr_managers(self):
        """BWMI = Business-Wall Media Internal — internal staff of
        the BW org. BWME = Business-Wall Media External, but in
        Erick's spec is still an internal-style role for editorial
        purposes."""
        assert BWRoleType.BWMI.value in DASHBOARD_ACCESS_ROLES
        assert BWRoleType.BWME.value in DASHBOARD_ACCESS_ROLES

    def test_excludes_external_pr_roles(self):
        """Bug #0157 narrowed the gate : external PR managers
        (BWPRi / BWPRe — Partnerships) must NOT reach the
        management dashboard. Pin so a re-introduction is caught."""
        # BWPRi and BWPRe carry the « external PR » semantics —
        # check both are excluded.
        external_roles = []
        for member in BWRoleType:
            name = member.name
            if name.startswith("BWPR"):
                external_roles.append(member.value)

        for role in external_roles:
            assert role not in DASHBOARD_ACCESS_ROLES, (
                f"External PR role {role!r} must not have dashboard access (#0157)"
            )

    def test_size_is_three(self):
        """Three roles, no more, no less. Pin so a future « let's
        also let BWADMIN in » doesn't sneak through unreviewed.
        Update this number when a 4th role is added — that's the
        point."""
        assert len(DASHBOARD_ACCESS_ROLES) == 3


class TestCanAccessBwDashboard:
    """The predicate consulted by the route guard."""

    def test_bw_owner_can_access(self):
        assert can_access_bw_dashboard(BWRoleType.BW_OWNER.value) is True

    def test_bwmi_can_access(self):
        assert can_access_bw_dashboard(BWRoleType.BWMI.value) is True

    def test_bwme_can_access(self):
        assert can_access_bw_dashboard(BWRoleType.BWME.value) is True

    def test_bwpri_cannot_access(self):
        """External PR managers : explicit denial. The role was
        originally inside the list pre-#0157 — pin so a regression
        is loud."""
        # BWPRi value is whatever the enum says ; resolve via the
        # enum so we don't hardcode the string spelling.
        for member in BWRoleType:
            if "PRI" in member.name.upper():
                assert can_access_bw_dashboard(member.value) is False, (
                    f"{member.name} should NOT have dashboard access"
                )

    def test_empty_string_cannot_access(self):
        """Defensive : an empty role string (e.g. unpopulated row)
        must NOT grant access. Pin so a future `if role_type or
        is_admin:` regression doesn't silently let through holes."""
        assert can_access_bw_dashboard("") is False

    def test_unknown_role_cannot_access(self):
        """Default-deny : anything not in the explicit list is
        refused. Pin the closed-world contract."""
        assert can_access_bw_dashboard("UNKNOWN_ROLE") is False
        assert can_access_bw_dashboard("ADMIN") is False
        assert can_access_bw_dashboard("bw_owner") is False  # case-sensitive

    def test_case_sensitivity(self):
        """The role values use the project's mixed-case enum spelling
        (`"BWMi"`, `"BWMe"`, `"BW_OWNER"`). Lowercase or full-upper
        impostors must be refused — pin so a future tightening to
        case-insensitive doesn't silently widen the gate."""
        # Case-impostors of legitimate values are refused.
        assert can_access_bw_dashboard("bw_owner") is False
        assert can_access_bw_dashboard("BWMI") is False
        assert can_access_bw_dashboard("bwmi") is False
        # The canonical spelling works (sanity).
        assert can_access_bw_dashboard("BWMi") is True
        assert can_access_bw_dashboard("BW_OWNER") is True

    def test_returns_bool_not_truthy(self):
        """Pin the return type. A caller doing `if can_access(...)
        is True:` (defensive type-check style) shouldn't silently
        break when the impl moves from `in` to `if ... return ...`."""
        result = can_access_bw_dashboard(BWRoleType.BW_OWNER.value)
        assert isinstance(result, bool)
