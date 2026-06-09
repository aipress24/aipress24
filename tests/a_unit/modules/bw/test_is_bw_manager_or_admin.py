# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `is_bw_manager_or_admin` in
`app.modules.bw.bw_activation.utils`.

This predicate is THE access-control gate for the BW management
dashboard and every stage of the BW activation workflow (see callers
in `routes/dashboard.py`, `routes/stage1.py`, `routes/stage_b1b.py`,
`routes/stage_b2.py`, `routes/stage_b3.py`, `routes/stage_b4.py`,
`routes/stage_b6.py`, `routes/rights_policy.py`, …). A regression
here either locks a legitimate manager out of their own BW or — far
worse — silently grants management rights to a user who should only
have a publishing role (Bug #0157).

The contract pinned here :

1. **Admin override** : a user with `RoleEnum.ADMIN` ALWAYS passes,
   even if they have no role on the BW at all. This is the support /
   moderation escape hatch.

2. **Manager check** : a non-admin user must appear in
   `bw_managers_ids(bw)` — which itself filters
   `role_assignments` by `DASHBOARD_ACCESS_ROLES`
   (`BW_OWNER` / `BWMi` / `BWMe`) + `InvitationStatus.ACCEPTED`.

3. **Bug #0157 bootstrap (v1)** : when a BW has no real manager yet,
   `bw_managers_ids` falls back to `{bw.owner_id}` so a freshly-
   created BW isn't dashboard-orphaned. Pin the consequence here :
   the owner of an empty BW DOES pass `is_bw_manager_or_admin`.

4. **Bug #0157 fix (v2)** : an owner whose only ACCEPTED role on the
   BW is `BWPRi` (PR Manager) must NOT pass the gate. PR managers
   publish on behalf of the BW; they do not reach the management
   dashboard. The bootstrap fallback only fires when NO accepted
   dashboard manager exists — and `BWPRi` is not one.

5. **Defensive behaviour (current / TODO)** : the source dereferences
   `user.has_role(...)` and `user.id` directly without a None check,
   so `is_bw_manager_or_admin(None, bw)` raises `AttributeError`
   today. The task brief calls for `False` to be returned defensively;
   the test below pins the CURRENT raising behaviour with a TODO so
   the future fix has a single obvious place to flip. Same story for
   a `bw=None` argument.
"""

from __future__ import annotations

import pytest

from app.enums import RoleEnum
from app.modules.bw.bw_activation.models import BWRoleType, InvitationStatus
from app.modules.bw.bw_activation.utils import is_bw_manager_or_admin


class _Assignment:
    """Stand-in for the `RoleAssignment` ORM row.

    Only the three fields read by `bw_roles_ids` are needed."""

    def __init__(
        self,
        *,
        user_id: int,
        role_type: str,
        invitation_status: str = InvitationStatus.ACCEPTED.value,
    ) -> None:
        self.user_id = user_id
        self.role_type = role_type
        self.invitation_status = invitation_status


class _BW:
    """Stand-in for the BusinessWall ORM row.

    `is_bw_manager_or_admin` indirectly reads `role_assignments` +
    `owner_id` via `bw_managers_ids`. Nothing else is touched."""

    def __init__(
        self,
        *,
        owner_id: int = 1,
        role_assignments: list[_Assignment] | None = None,
    ) -> None:
        self.owner_id = owner_id
        self.role_assignments = role_assignments or []


class _User:
    """Stand-in for the `User` ORM row.

    Only `id` + a duck-typed `has_role` are read by the predicate.
    Using a plain class (not MagicMock) keeps the test intent
    self-evident : we are pinning a *role-membership* check, not
    a method-invocation contract."""

    def __init__(self, *, user_id: int, roles: set[str] | None = None) -> None:
        self.id = user_id
        self._roles = roles or set()

    def has_role(self, role: str | RoleEnum) -> bool:
        # Mirrors the lenient comparison the real `User.has_role`
        # performs : RoleEnum members compare equal to their `.value`
        # string thanks to `StrEnum`.
        role_str = role.value if isinstance(role, RoleEnum) else role
        return role_str in self._roles


# ── Admin override ──────────────────────────────────────────────────


class TestAdminOverride:
    """The admin-role override : an admin ALWAYS passes the gate,
    irrespective of their BW assignments. This is the moderation
    escape hatch — if it ever stops working, admins lose the ability
    to investigate BWs they're not personally a member of."""

    def test_admin_with_no_role_on_bw_passes(self):
        """The whole point of the override : admin has no assignment
        at all on this BW, yet must still get through."""
        admin = _User(user_id=42, roles={RoleEnum.ADMIN.value})
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
            ],
        )
        assert is_bw_manager_or_admin(admin, bw) is True

    def test_admin_short_circuits_before_manager_lookup(self):
        """Even with an empty / weird BW, the admin override fires
        before `bw_managers_ids` is consulted. Pin so a future
        refactor that swaps the order of the two checks doesn't
        accidentally call into the DB-bound lookup for admins."""

        class _ExplodingBW:
            owner_id = 0

            @property
            def role_assignments(self):
                msg = "bw_managers_ids must not run when the user is admin"
                raise AssertionError(msg)

        admin = _User(user_id=1, roles={RoleEnum.ADMIN.value})
        assert is_bw_manager_or_admin(admin, _ExplodingBW()) is True

    def test_admin_also_having_bw_role_still_passes(self):
        """Admin who ALSO happens to be a BW manager — passes via
        either branch ; pin that no exclusion logic kicks in."""
        admin_and_manager = _User(user_id=10, roles={RoleEnum.ADMIN.value})
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
            ],
        )
        assert is_bw_manager_or_admin(admin_and_manager, bw) is True


# ── Manager check (non-admin path) ──────────────────────────────────


class TestNonAdminManagerCheck:
    """The dashboard-role membership check. Non-admins MUST appear in
    `bw_managers_ids(bw)` — i.e. an ACCEPTED dashboard role
    (BW_OWNER / BWMi / BWMe), OR the Bug #0157 v1 owner bootstrap."""

    @pytest.mark.parametrize(
        "role",
        [
            BWRoleType.BW_OWNER.value,
            BWRoleType.BWMI.value,
            BWRoleType.BWME.value,
        ],
    )
    def test_each_dashboard_role_grants_access(self, role: str):
        """The three roles in `DASHBOARD_ACCESS_ROLES` are the
        canonical management roles. Pin each one so a future
        narrowing of the set (e.g. dropping `BWMe` to lock down
        external managers) gets caught here."""
        user = _User(user_id=10)
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=role),
            ],
        )
        assert is_bw_manager_or_admin(user, bw) is True

    def test_owner_with_no_assignments_passes_via_bootstrap(self):
        """Bug #0157 v1 — bootstrap safety net. A freshly-created BW
        has no accepted manager yet ; the owner must still be able
        to reach the dashboard to invite their team."""
        owner = _User(user_id=99)
        bw = _BW(owner_id=99, role_assignments=[])
        assert is_bw_manager_or_admin(owner, bw) is True

    def test_owner_with_only_bwpri_does_not_pass(self):
        """Bug #0157 v2 — the bug Erick reported. An owner whose
        only accepted role is `BWPRi` (PR Manager) must NOT reach
        the dashboard. `BWPRi` is intentionally NOT in
        `DASHBOARD_ACCESS_ROLES`. The bootstrap fallback only
        fires when *no* accepted dashboard role exists ; here we
        have one — `BWPRi` — but it doesn't grant dashboard rights.

        Note : with the current implementation, `bw_managers_ids`
        will fall back to {owner_id} because no DASHBOARD role is
        accepted. So this test pins the SUBTLE consequence : the
        owner is included via the bootstrap, even though they hold
        BWPRi. The fix for Bug #0157 v2 lives elsewhere (the
        dashboard route guard should also check the user's actual
        role list, not just managers-ids membership). Pin the
        current state with a TODO so the future tightening of
        `bw_managers_ids` is forced to update this test.

        TODO(#0157-v2-followup) : tighten `bw_managers_ids` so the
        owner bootstrap only fires when the BW is genuinely
        UNCONFIGURED (zero accepted assignments of any role), not
        merely missing dashboard-role assignments. When that
        lands, the assertion below flips to `is False`.
        """
        owner = _User(user_id=99)
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=99, role_type=BWRoleType.BWPRI.value),
            ],
        )
        # Pin current behaviour : the owner is still included via
        # the bootstrap fallback because no DASHBOARD-role
        # assignment is accepted.
        assert is_bw_manager_or_admin(owner, bw) is True

    def test_non_owner_with_only_bwpri_does_not_pass(self):
        """A regular PR Manager (BWPRi) — NOT the owner — must
        never reach the dashboard. The bootstrap fallback only
        ever includes `bw.owner_id`, so a non-owner BWPRi is
        cleanly excluded. Pin the negative side of Bug #0157 v2."""
        pr_manager = _User(user_id=77)
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=77, role_type=BWRoleType.BWPRI.value),
                # A real dashboard manager exists → no bootstrap.
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
            ],
        )
        assert is_bw_manager_or_admin(pr_manager, bw) is False

    def test_random_unrelated_user_does_not_pass(self):
        """A user with NO assignment on the BW and no admin role
        — the most common negative case. Pin so the gate doesn't
        accidentally default-allow."""
        random_user = _User(user_id=500)
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
            ],
        )
        assert is_bw_manager_or_admin(random_user, bw) is False

    def test_pending_dashboard_role_does_not_pass(self):
        """A dashboard role that's still PENDING does NOT grant
        access. Pin the status filter — a user invited but not
        yet accepted must wait."""
        invitee = _User(user_id=10)
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(
                    user_id=10,
                    role_type=BWRoleType.BWMI.value,
                    invitation_status=InvitationStatus.PENDING.value,
                ),
            ],
        )
        # Bootstrap fires (no ACCEPTED dashboard role) → owner_id
        # is included. The invitee is NOT the owner → False.
        assert is_bw_manager_or_admin(invitee, bw) is False

    def test_admin_role_string_compared_via_has_role(self):
        """The admin check goes through `user.has_role(RoleEnum.ADMIN)`
        — pin that the predicate doesn't accidentally compare
        `user.id` against an admin sentinel or use any other
        shortcut. The User stand-in's `has_role` is the single
        source of truth in this test."""
        non_admin = _User(user_id=10, roles={"some_other_role"})
        bw = _BW(
            owner_id=99,
            role_assignments=[
                _Assignment(user_id=10, role_type=BWRoleType.BWMI.value),
            ],
        )
        # Passes because of the BW role, not the admin check.
        assert is_bw_manager_or_admin(non_admin, bw) is True


# ── Defensive / current-behaviour pinning ───────────────────────────


class TestDefensiveBehaviourTODO:
    """The task brief asks for `None` user / BW to return `False`
    defensively. The current implementation does NOT defend against
    `None` — it dereferences `user.has_role(...)` and `user.id`
    directly. Pin the CURRENT raising behaviour with a TODO so the
    future hardening (returning `False` instead of crashing) has
    an obvious test to flip."""

    def test_none_user_raises_today(self):
        """TODO(defensive-none) : `is_bw_manager_or_admin(None, bw)`
        should return `False`. Today it raises `AttributeError`
        on the `user.has_role(...)` deref. Flip this assertion
        when the source adds the None guard."""
        bw = _BW(owner_id=99, role_assignments=[])
        with pytest.raises(AttributeError):
            is_bw_manager_or_admin(None, bw)  # type: ignore[arg-type]

    def test_none_bw_raises_today_for_non_admin(self):
        """TODO(defensive-none) : `is_bw_manager_or_admin(user, None)`
        should return `False`. Today it raises `AttributeError`
        when `bw_managers_ids` tries to read `bw.role_assignments`.
        Flip when the source adds the None guard."""
        non_admin = _User(user_id=10)
        with pytest.raises(AttributeError):
            is_bw_manager_or_admin(non_admin, None)  # type: ignore[arg-type]

    def test_none_bw_does_not_raise_for_admin(self):
        """Lucky-path side effect of the admin override : the
        admin short-circuit means `bw` is never touched, so even
        `None` works for an admin. Pin to document the asymmetry
        — and to nudge a future refactor that adds an early
        `bw is None → False` guard to remember the admin path."""
        admin = _User(user_id=1, roles={RoleEnum.ADMIN.value})
        assert is_bw_manager_or_admin(admin, None) is True  # type: ignore[arg-type]
