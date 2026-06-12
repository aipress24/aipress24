# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `get_user_rights_on_bw` in
`app.modules.bw.bw_activation.user_utils`.

The function is already pure — it walks `bw.role_assignments`
(already-loaded), reads attributes, and returns a list of
human-readable « rights » strings the dashboard surfaces. No DB
calls inside the body. Stubs are the right test fixture.

The three rules :

1. **Ownership** — if `bw.owner_id == user.id`, prepend
   « Propriétaire (Business Wall Owner) ».
2. **Accepted roles** — for each `RoleAssignment` with
   `user_id == user.id` AND `invitation_status == "accepted"`, add
   « Rôle : <label> ». Deduped by `role_type` so the OWNER row
   doesn't double-up with rule 1.
3. **Granted PR missions** — only for `BWPRI` / `BWPRE` role
   assignments : for each `Permission` with `is_granted=True`, add
   « Mission : <label> » (deduped by `permission_type`).

Pinning each branch at a_unit tier so a refactor that drops a rule
(or flips the dedup order) surfaces immediately.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.modules.bw.bw_activation.models import InvitationStatus
from app.modules.bw.bw_activation.models.role import BWRoleType
from app.modules.bw.bw_activation.user_utils import get_user_rights_on_bw


def _user(id: int = 7) -> SimpleNamespace:
    return SimpleNamespace(id=id)


def _bw(
    *,
    owner_id: int | None = None,
    role_assignments: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        owner_id=owner_id,
        role_assignments=role_assignments or [],
    )


def _assignment(
    *,
    user_id: int,
    role_type: str,
    invitation_status: str = InvitationStatus.ACCEPTED.value,
    permissions: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id,
        role_type=role_type,
        invitation_status=invitation_status,
        permissions=permissions or [],
    )


def _permission(*, permission_type: str, is_granted: bool = True) -> SimpleNamespace:
    return SimpleNamespace(permission_type=permission_type, is_granted=is_granted)


# ---------------------------------------------------------------------------
# Rule 1 : ownership
# ---------------------------------------------------------------------------


class TestOwnership:
    def test_owner_gets_proprietaire_label(self):
        user = _user(id=7)
        bw = _bw(owner_id=7)
        rights = get_user_rights_on_bw(user, bw)
        assert any("Propriétaire" in r for r in rights)
        assert any("Business Wall Owner" in r for r in rights)

    def test_non_owner_does_not_get_proprietaire(self):
        user = _user(id=7)
        bw = _bw(owner_id=999)
        rights = get_user_rights_on_bw(user, bw)
        assert not any("Propriétaire" in r for r in rights)

    def test_no_owner_no_assignments_yields_empty_list(self):
        rights = get_user_rights_on_bw(_user(id=7), _bw(owner_id=None))
        assert rights == []


# ---------------------------------------------------------------------------
# Rule 2 : accepted roles
# ---------------------------------------------------------------------------


class TestAcceptedRoles:
    def test_accepted_role_adds_role_label(self):
        user = _user(id=7)
        bw = _bw(
            owner_id=None,
            role_assignments=[_assignment(user_id=7, role_type=BWRoleType.BWMI.value)],
        )
        rights = get_user_rights_on_bw(user, bw)
        assert "Rôle : Business Wall Manager (internal)" in rights

    def test_pending_role_is_skipped(self):
        """A role still in PENDING / REJECTED / EXPIRED state isn't
        operational yet — the user has no rights from it."""
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(
                    user_id=7,
                    role_type=BWRoleType.BWMI.value,
                    invitation_status=InvitationStatus.PENDING.value,
                )
            ],
        )
        assert get_user_rights_on_bw(user, bw) == []

    def test_rejected_role_is_skipped(self):
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(
                    user_id=7,
                    role_type=BWRoleType.BWMI.value,
                    invitation_status=InvitationStatus.REJECTED.value,
                )
            ],
        )
        assert get_user_rights_on_bw(user, bw) == []

    def test_assignment_for_other_user_is_skipped(self):
        """A BW's role_assignments list can carry rows for ANY user ;
        only rows matching the queried user contribute."""
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(user_id=999, role_type=BWRoleType.BWMI.value)
            ],
        )
        assert get_user_rights_on_bw(user, bw) == []

    def test_multiple_role_types_for_same_user_each_listed(self):
        """A user can hold several roles simultaneously (e.g. BWMI + BWPRI).
        Both show up, deduped by role_type."""
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(user_id=7, role_type=BWRoleType.BWMI.value),
                _assignment(user_id=7, role_type=BWRoleType.BWPRI.value),
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        assert "Rôle : Business Wall Manager (internal)" in rights
        assert "Rôle : PR Manager (internal)" in rights

    def test_duplicate_role_type_is_deduped(self):
        """If two accepted RoleAssignments somehow exist for the same
        user + same role_type (bad data), the label appears only once."""
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(user_id=7, role_type=BWRoleType.BWMI.value),
                _assignment(user_id=7, role_type=BWRoleType.BWMI.value),
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        role_labels = [r for r in rights if r.startswith("Rôle :")]
        assert role_labels == ["Rôle : Business Wall Manager (internal)"]


class TestOwnershipDedupesWithRole:
    """Rule 1 (ownership → BW_OWNER) and Rule 2 (accepted role of type
    BW_OWNER) must not double-up — they overlap by design when the
    owner also has an explicit RoleAssignment row."""

    def test_owner_with_explicit_bw_owner_role_yields_one_row(self):
        user = _user(id=7)
        bw = _bw(
            owner_id=7,
            role_assignments=[
                _assignment(user_id=7, role_type=BWRoleType.BW_OWNER.value),
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        # Exactly one Propriétaire-shaped row + zero further Rôle-shaped
        # rows for BW_OWNER.
        prop_rows = [r for r in rights if "Propriétaire" in r]
        role_owner_rows = [
            r for r in rights if r.startswith("Rôle :") and "Business Wall Owner" in r
        ]
        assert len(prop_rows) == 1
        assert role_owner_rows == []


# ---------------------------------------------------------------------------
# Rule 3 : granted PR missions
# ---------------------------------------------------------------------------


class TestGrantedMissions:
    def test_pri_with_granted_permission_yields_mission_label(self):
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(
                    user_id=7,
                    role_type=BWRoleType.BWPRI.value,
                    permissions=[
                        _permission(permission_type="press_release"),
                    ],
                )
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        assert "Mission : Publier des communiqués de presse" in rights

    def test_pre_also_gets_mission_labels(self):
        """The granular-permission branch fires for both internal
        (BWPRI) AND external (BWPRE) PR managers — they share the same
        publication scope."""
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(
                    user_id=7,
                    role_type=BWRoleType.BWPRE.value,
                    permissions=[_permission(permission_type="events")],
                )
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        assert "Mission : Publier des événements" in rights

    def test_revoked_permission_does_not_show_mission(self):
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(
                    user_id=7,
                    role_type=BWRoleType.BWPRI.value,
                    permissions=[
                        _permission(permission_type="missions", is_granted=False),
                    ],
                )
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        assert not any("Mission :" in r for r in rights)

    def test_non_pr_role_does_not_emit_missions(self):
        """BWMI / BWME are management roles — they don't have the
        granular publication permissions, so no Mission rows. Pin so
        a refactor adding more permissions doesn't accidentally leak
        them onto BWMI's right list."""
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(
                    user_id=7,
                    role_type=BWRoleType.BWMI.value,
                    # If permissions WERE inspected, this would yield
                    # a Mission row.
                    permissions=[_permission(permission_type="press_release")],
                )
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        assert not any("Mission :" in r for r in rights)

    def test_multiple_missions_each_listed_and_deduped(self):
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(
                    user_id=7,
                    role_type=BWRoleType.BWPRI.value,
                    permissions=[
                        _permission(permission_type="press_release"),
                        _permission(permission_type="events"),
                        # Duplicate permission_type — must dedup.
                        _permission(permission_type="press_release"),
                    ],
                )
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        mission_rows = [r for r in rights if r.startswith("Mission :")]
        assert sorted(mission_rows) == sorted(
            [
                "Mission : Publier des communiqués de presse",
                "Mission : Publier des événements",
            ]
        )

    def test_unknown_permission_type_falls_back_to_raw_value(self):
        """`MISSION_LABELS.get(permission_type, permission_type)` —
        a future permission type that hasn't been added to the label
        dict still surfaces in the UI rather than being silently
        dropped."""
        user = _user(id=7)
        bw = _bw(
            role_assignments=[
                _assignment(
                    user_id=7,
                    role_type=BWRoleType.BWPRI.value,
                    permissions=[
                        _permission(permission_type="unmapped_perm_xyz"),
                    ],
                )
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        assert "Mission : unmapped_perm_xyz" in rights


# ---------------------------------------------------------------------------
# Empty / edge cases
# ---------------------------------------------------------------------------


class TestEmptyAndEdgeCases:
    def test_empty_role_assignments_yields_empty_list(self):
        user = _user(id=7)
        bw = _bw(owner_id=None, role_assignments=[])
        assert get_user_rights_on_bw(user, bw) == []

    def test_none_role_assignments_treated_as_empty(self):
        """The relationship may be None on a freshly-built BW (vs.
        empty list on a persisted one). Pin so the iteration doesn't
        crash with TypeError."""
        user = _user(id=7)
        bw = SimpleNamespace(owner_id=None, role_assignments=None)
        assert get_user_rights_on_bw(user, bw) == []

    def test_returns_a_list(self):
        """The dashboard template iterates the result — pin the
        return type so a refactor that switches to a generator
        doesn't break Jinja's `len()`."""
        result = get_user_rights_on_bw(_user(id=7), _bw())
        assert isinstance(result, list)

    def test_rights_order_owner_first_then_roles_then_missions(self):
        """The UI lists rights top-down ; for a user who is owner +
        BWPRI with a granted permission, the order should be :
        Propriétaire → Rôle → Mission. Pin so a refactor that
        reorders silently doesn't break the dashboard's expectation."""
        user = _user(id=7)
        bw = _bw(
            owner_id=7,
            role_assignments=[
                _assignment(
                    user_id=7,
                    role_type=BWRoleType.BWPRI.value,
                    permissions=[_permission(permission_type="press_release")],
                )
            ],
        )
        rights = get_user_rights_on_bw(user, bw)
        assert rights[0].startswith("Propriétaire")
        # Next non-Propriétaire row is the Rôle line.
        post_owner = rights[1:]
        assert post_owner[0].startswith("Rôle :")
        # Mission lines come after the role line.
        mission_indices = [i for i, r in enumerate(rights) if r.startswith("Mission :")]
        role_indices = [i for i, r in enumerate(rights) if r.startswith("Rôle :")]
        assert min(role_indices) < min(mission_indices)
