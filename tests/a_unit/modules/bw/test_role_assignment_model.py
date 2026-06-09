# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests pinning the *shape* of the `RoleAssignment` SQLAlchemy
mapped class (and its sibling `RolePermission`) at
`app.modules.bw.bw_activation.models.role`.

These tests do NOT touch a database. They introspect the SQLAlchemy
metadata to lock in :

- Table name (used by Alembic migrations and raw SQL elsewhere).
- The set of columns and their nullability.
- The default value for `invitation_status` (must equal
  `InvitationStatus.PENDING.value`) — drift here silently breaks
  invitation workflows because new rows would land in a status the
  dashboard filters don't recognise.
- Foreign-key targets and ON DELETE behaviour (CASCADE is required so
  deleting a Business Wall cleans up its role assignments).
- Relationship cascades on `permissions` (delete-orphan is required so
  removing a role assignment cleans up its permission rows).
- Inheritance from `UUIDAuditBase` — the audit columns (`created_at`,
  `updated_at`) and the UUID primary key are part of the contract.

DB-bound behaviour (constraint violation, defaults at INSERT time,
ondelete cascade actually firing) is covered by `b_integration`
tests, not here.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import inspect as sa_inspect

from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
    PermissionType,
    RoleAssignment,
    RolePermission,
)


def _column(model, name):
    """Helper — fetch a column from a mapped class without instantiating
    a row."""
    return model.__table__.columns[name]


class TestRoleAssignmentClassShape:
    """The class must be a SQLAlchemy mapped class that inherits from
    `UUIDAuditBase`. That parent supplies the UUID `id` primary key and
    the `created_at` / `updated_at` audit columns the BW dashboard
    relies on for « who invited who, when ».
    """

    def test_inherits_from_uuid_audit_base(self):
        """Pin the parent so a refactor to a different base (or no base)
        catches here, not at first INSERT."""
        assert issubclass(RoleAssignment, UUIDAuditBase)

    def test_tablename(self):
        """Hard-coded `__tablename__` is referenced by Alembic
        migrations and by raw SQL in dashboard widgets — renaming it
        without a migration would silently break SELECTs."""
        assert RoleAssignment.__tablename__ == "bw_role_assignment"

    def test_is_sqlalchemy_mapped(self):
        """`sa_inspect` succeeds only on mapped classes — a defensive
        gate."""
        mapper = sa_inspect(RoleAssignment)
        assert mapper is not None
        assert mapper.class_ is RoleAssignment

    def test_no_custom_table_args(self):
        """At the time of writing there are no composite unique
        constraints or indexes declared. Pin the absence so adding one
        later is a deliberate, reviewed change (and reviewers don't
        forget to also update the dashboard query plan)."""
        assert getattr(RoleAssignment, "__table_args__", None) is None


class TestRoleAssignmentColumns:
    """The column set is the table's contract with the rest of the
    codebase. Pin it explicitly — every dashboard query, every form
    handler, every Stripe webhook callback reads at least one of
    these columns by name."""

    EXPECTED_COLUMNS: ClassVar[set[str]] = {
        # From UUIDAuditBase
        "id",
        "created_at",
        "updated_at",
        # From RoleAssignment itself
        "business_wall_id",
        "user_id",
        "role_type",
        "invitation_status",
        "invited_at",
        "accepted_at",
        "rejected_at",
    }

    def test_expected_columns_all_present(self):
        """At minimum, every name the BW codebase reads must exist.
        We allow extras (e.g. `sa_orm_sentinel` from
        advanced-alchemy)."""
        actual = set(RoleAssignment.__table__.columns.keys())
        missing = self.EXPECTED_COLUMNS - actual
        assert not missing, f"Missing columns on RoleAssignment: {missing}"

    @pytest.mark.parametrize(
        "col_name",
        [
            "business_wall_id",
            "user_id",
            "role_type",
            "invitation_status",
        ],
    )
    def test_required_columns_are_not_nullable(self, col_name):
        """The four « core identity » columns must be NOT NULL — a row
        without a target BW / user / role / status is meaningless and
        would crash downstream consumers."""
        assert _column(RoleAssignment, col_name).nullable is False

    @pytest.mark.parametrize(
        "col_name",
        ["invited_at", "accepted_at", "rejected_at"],
    )
    def test_lifecycle_timestamps_are_nullable(self, col_name):
        """Each lifecycle timestamp is set only when the transition
        happens — they MUST be nullable so a freshly-created row
        (pre-acceptance, pre-rejection) is valid."""
        assert _column(RoleAssignment, col_name).nullable is True


class TestInvitationStatusDefault:
    """The `invitation_status` default is the lynchpin of the
    invitation workflow — new rows must land in `PENDING` so the
    « accept invitation » flow has work to do. If a refactor swaps
    the default to ACCEPTED, every new invite would silently grant
    access without user confirmation."""

    def test_default_is_pending_string(self):
        """Pin the exact string the column defaults to."""
        col = _column(RoleAssignment, "invitation_status")
        assert col.default is not None
        # ScalarElementColumnDefault exposes the value via .arg
        assert col.default.arg == "pending"

    def test_default_equals_invitation_status_pending_value(self):
        """The default must track the enum — protects against a
        refactor that renames the enum value but forgets to update
        the column default."""
        col = _column(RoleAssignment, "invitation_status")
        assert col.default.arg == InvitationStatus.PENDING.value


class TestForeignKeys:
    """Pin the FK targets and ondelete behaviour. ON DELETE CASCADE
    on `business_wall_id` is critical : when an organisation deletes
    its BW, every role assignment row must disappear, otherwise we
    leak stale access grants."""

    def test_business_wall_fk_target(self):
        col = _column(RoleAssignment, "business_wall_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "bw_business_wall"
        assert fks[0].column.name == "id"

    def test_business_wall_fk_cascade_on_delete(self):
        col = _column(RoleAssignment, "business_wall_id")
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete == "CASCADE"

    def test_user_id_has_no_fk(self):
        """Per the source comment « no FK constraint for POC ».
        Pin this so a future « let's add the FK » is a deliberate
        decision (it requires a migration backfill — User IDs may
        already be stale)."""
        col = _column(RoleAssignment, "user_id")
        assert list(col.foreign_keys) == []


class TestRelationships:
    """Pin the ORM-level relationships : the BW back-ref name and the
    permissions cascade. The cascade is what makes `delete
    role_assignment` clean up the `RolePermission` rows tied to it."""

    def test_business_wall_relationship_exists(self):
        mapper = sa_inspect(RoleAssignment)
        assert "business_wall" in mapper.relationships
        rel = mapper.relationships["business_wall"]
        assert rel.mapper.class_.__name__ == "BusinessWall"

    def test_permissions_relationship_exists(self):
        mapper = sa_inspect(RoleAssignment)
        assert "permissions" in mapper.relationships
        rel = mapper.relationships["permissions"]
        assert rel.mapper.class_ is RolePermission

    def test_permissions_cascade_includes_delete_orphan(self):
        """Without `delete-orphan`, detaching a permission row from
        its parent assignment would leak it as a dangling row.
        Pin so a future refactor doesn't drop the cascade."""
        mapper = sa_inspect(RoleAssignment)
        cascade = mapper.relationships["permissions"].cascade
        assert cascade.delete_orphan is True
        assert cascade.delete is True


class TestRepr:
    """The `__repr__` is read in log lines and in the debug toolbar.
    Pin its shape so a regression doesn't make grep-by-id useless."""

    def test_repr_contains_id_role_and_user(self):
        """Build a stand-in (not a real row — no DB) and assert the
        format. We use a duck-typed object for clarity."""

        class _StandIn:
            id = "abc-123"
            role_type = BWRoleType.BW_OWNER.value
            user_id = 42

        rendered = RoleAssignment.__repr__(_StandIn())  # type: ignore[arg-type]
        assert "abc-123" in rendered
        assert "BW_OWNER" in rendered
        assert "42" in rendered
        assert rendered.startswith("<RoleAssignment")
        assert rendered.endswith(">")


class TestRolePermissionClassShape:
    """`RolePermission` is the granular permission row for PR Managers.
    It must also inherit from `UUIDAuditBase` (audit trail is required
    so we can answer « who granted MEDIA_CONTACTS to this PR Manager,
    and when »)."""

    def test_inherits_from_uuid_audit_base(self):
        assert issubclass(RolePermission, UUIDAuditBase)

    def test_tablename(self):
        assert RolePermission.__tablename__ == "bw_role_permission"

    def test_expected_columns_present(self):
        expected = {
            "id",
            "created_at",
            "updated_at",
            "role_assignment_id",
            "permission_type",
            "is_granted",
        }
        actual = set(RolePermission.__table__.columns.keys())
        missing = expected - actual
        assert not missing, f"Missing columns on RolePermission: {missing}"

    @pytest.mark.parametrize(
        "col_name",
        ["role_assignment_id", "permission_type"],
    )
    def test_required_columns_not_nullable(self, col_name):
        assert _column(RolePermission, col_name).nullable is False

    def test_is_granted_default_is_false(self):
        """Permissions default to *denied*. This is the secure default
        — a new PermissionType row created without explicit grant must
        NOT silently grant access."""
        col = _column(RolePermission, "is_granted")
        assert col.default is not None
        assert col.default.arg is False

    def test_role_assignment_fk_cascade(self):
        """Deleting a role assignment must clear its permission rows —
        otherwise we leak orphan permissions."""
        col = _column(RolePermission, "role_assignment_id")
        fk = next(iter(col.foreign_keys))
        assert fk.column.table.name == "bw_role_assignment"
        assert fk.ondelete == "CASCADE"

    def test_role_assignment_relationship_back_populates(self):
        mapper = sa_inspect(RolePermission)
        rel = mapper.relationships["role_assignment"]
        assert rel.mapper.class_ is RoleAssignment

    def test_repr_contains_granted_or_denied(self):
        """Pin the wording — log scrapers may grep for « granted »."""

        class _StandIn:
            id = "perm-1"
            permission_type = PermissionType.MEDIA_CONTACTS.value
            is_granted = True

        rendered = RolePermission.__repr__(_StandIn())  # type: ignore[arg-type]
        assert "granted" in rendered
        assert "media_contacts" in rendered

        _StandIn.is_granted = False
        rendered2 = RolePermission.__repr__(_StandIn())  # type: ignore[arg-type]
        assert "denied" in rendered2
