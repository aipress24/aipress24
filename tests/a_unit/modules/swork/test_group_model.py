# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the `Group` model and the two association tables in
`app.modules.swork.models.groups`.

`Group` is the SQLAlchemy model behind every social workspace
« groupe » — communities of members that can be public, private or
secret. The model has very little Python logic of its own ; almost
everything important about it lives in the *schema* (column defaults,
nullability, types, foreign-key cascades, unique constraints).

These tests pin that schema CONTRACT by introspecting `__table__`
rather than touching a database. They protect against quiet drift in
properties that Erick's product spec relies on, in particular :

* `privacy` defaults to ``"private"`` (3-state public/private/secret
  spec, default-safe).
* `description` is stored through `SanitizedHTML` (XSS-safety on
  write — must NEVER be downgraded to plain `String`).
* `group_members_table` enforces unique `(user_id, group_id)` so a
  user can't double-join a group, and cascades on user/group deletion.
* `group_exclusions_table` mirrors the same uniqueness + cascade
  contract for banned users.

Pinning these at the model layer means a refactor that accidentally
drops a default or a constraint will fail fast, instead of failing in
production with corrupted membership rows or unsanitized HTML.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.models.base import Base
from app.models.mixins import Addressable, IdMixin, LifeCycleMixin, Owned
from app.modules.swork.models.groups import (
    Group,
    group_exclusions_table,
    group_members_table,
)
from app.services.html_sanitize import SanitizedHTML


def _default_of(column: sa.Column):
    """Return the scalar default value of a column, or ``None``.

    SQLAlchemy wraps column defaults in a `ColumnDefault` object whose
    ``arg`` attribute holds the raw value (scalar or callable). Tests
    only care about the scalar, so we unwrap once and return ``None``
    when no default is declared.
    """
    if column.default is None:
        return None
    return column.default.arg


# ---------------------------------------------------------------------------
# Group model
# ---------------------------------------------------------------------------


class TestGroupTableMeta:
    """Pin the table-level identity of `Group`.

    The tablename is referenced by Alembic migrations, raw SQL queries,
    and the admin UI — renaming it is a breaking change. We also pin
    the MRO so a refactor that drops one of the mixins (e.g. dropping
    `LifeCycleMixin` and losing `deleted_at`) fails here first.
    """

    def test_tablename(self):
        assert Group.__tablename__ == "soc_group"

    @pytest.mark.parametrize(
        "mixin",
        [IdMixin, Owned, LifeCycleMixin, Addressable, Base],
    )
    def test_inherits_expected_mixins(self, mixin):
        """`Group` must keep all 5 mixins. Each contributes columns
        (id, owner_id, lifecycle timestamps, address fields) that the
        rest of the app reads — dropping one silently would corrupt
        templates and queries."""
        assert issubclass(Group, mixin)


class TestGroupOwnColumns:
    """Pin the columns declared directly on `Group` (not inherited)."""

    OWN_COLUMNS = (
        "name",
        "privacy",
        "description",
        "logo_url",
        "cover_image_url",
        "num_members",
        "num_posts",
    )

    @pytest.mark.parametrize("col_name", OWN_COLUMNS)
    def test_column_exists(self, col_name):
        """Every documented field must be present on the table."""
        assert col_name in Group.__table__.columns

    @pytest.mark.parametrize("col_name", OWN_COLUMNS)
    def test_own_columns_are_not_nullable(self, col_name):
        """All declared business fields are required (no NULLs); the
        defaults make them effectively optional from Python but the DB
        constraint stays NOT NULL so analytics queries don't have to
        coalesce."""
        assert Group.__table__.columns[col_name].nullable is False

    def test_name_is_indexed(self):
        """`name` is indexed because group lookups by name happen in
        the directory search and in unique-name checks."""
        assert Group.__table__.columns["name"].index is True

    def test_privacy_default_is_private(self):
        """Erick's spec : public / private / secret, defaulting to
        PRIVATE for safety so a user who forgets to set privacy
        doesn't accidentally expose a group."""
        assert _default_of(Group.__table__.columns["privacy"]) == "private"

    def test_description_uses_sanitized_html_type(self):
        """`description` is rendered as Quill HTML in the UI. Storing
        it through `SanitizedHTML` (a `TypeDecorator`) strips XSS on
        write. Downgrading this column to plain `String` would
        re-introduce stored-XSS — pin it hard."""
        col = Group.__table__.columns["description"]
        assert isinstance(col.type, SanitizedHTML)

    @pytest.mark.parametrize(
        ("col_name", "expected_default"),
        [
            ("description", ""),
            ("logo_url", ""),
            ("cover_image_url", ""),
            ("num_members", 0),
            ("num_posts", 0),
        ],
    )
    def test_scalar_defaults(self, col_name, expected_default):
        """All non-name, non-privacy own fields default to empty/zero
        so a `Group(name=...)` constructor call is enough to produce
        a valid row."""
        assert _default_of(Group.__table__.columns[col_name]) == expected_default

    def test_name_has_no_default(self):
        """`name` is the only own column without a default — every
        group MUST have a name supplied explicitly. If a default ever
        appears it would mask missing-name bugs in the create form."""
        assert _default_of(Group.__table__.columns["name"]) is None


class TestGroupInheritedColumns:
    """Sanity-check that the mixin columns are wired up.

    We don't pin every detail of the mixins themselves (that's covered
    elsewhere), but we do pin the column NAMES so a `Group` row has
    the lifecycle + ownership + addressability surface the rest of
    the codebase assumes.
    """

    @pytest.mark.parametrize(
        "col_name",
        [
            "id",
            "owner_id",
            "created_at",
            "modified_at",
            "deleted_at",
            "address",
            "city",
            "country",
            "zip_code",
        ],
    )
    def test_inherited_column_present(self, col_name):
        assert col_name in Group.__table__.columns


# ---------------------------------------------------------------------------
# group_members_table
# ---------------------------------------------------------------------------


class TestGroupMembersTable:
    """Pin the M2M membership table.

    Membership is the single most-queried join in the swork module
    (« who is in this group ? », « what groups am I in ? »). The
    contract here protects against:

    * double-join races (UniqueConstraint),
    * orphaned rows when a user or group is deleted (ON DELETE CASCADE),
    * primary-key drift on either side (ON UPDATE CASCADE),
    * silent role corruption (role NOT NULL, default "member").
    """

    def test_tablename(self):
        assert group_members_table.name == "soc_group_members"

    @pytest.mark.parametrize(
        "col_name",
        ["user_id", "group_id", "role"],
    )
    def test_column_exists(self, col_name):
        assert col_name in group_members_table.columns

    def test_has_exactly_three_columns(self):
        """If a column is added without updating the contract — e.g.
        a `joined_at` timestamp — this test forces a conscious
        decision about indexing and defaults."""
        assert len(group_members_table.columns) == 3

    def test_role_default_is_member(self):
        """New memberships default to the plain « member » role.
        Promotion to admin/owner is an explicit follow-up action."""
        assert _default_of(group_members_table.columns["role"]) == "member"

    def test_role_is_not_nullable(self):
        """`role` must always have a value — code paths that branch
        on role would otherwise need defensive None-checks everywhere."""
        assert group_members_table.columns["role"].nullable is False

    def test_unique_user_group_pair(self):
        """A user cannot join the same group twice. Pinning via the
        constraint set (not just an index) ensures the DB rejects the
        duplicate insert atomically — race-safe."""
        unique_pairs = {
            tuple(sorted(c.name for c in cons.columns))
            for cons in group_members_table.constraints
            if isinstance(cons, sa.UniqueConstraint)
        }
        assert ("group_id", "user_id") in unique_pairs

    @pytest.mark.parametrize(
        ("col_name", "expected_table"),
        [("user_id", "aut_user"), ("group_id", "soc_group")],
    )
    def test_foreign_keys_target_expected_tables(self, col_name, expected_table):
        col = group_members_table.columns[col_name]
        fk_tables = {fk.column.table.name for fk in col.foreign_keys}
        assert expected_table in fk_tables

    @pytest.mark.parametrize("col_name", ["user_id", "group_id"])
    def test_foreign_keys_cascade_on_delete_and_update(self, col_name):
        """Deleting a user or a group must remove their membership
        rows ; renumbering the surrogate keys (rare but possible in
        Alembic migrations) must propagate. Without CASCADE we'd leak
        orphaned join rows."""
        col = group_members_table.columns[col_name]
        for fk in col.foreign_keys:
            assert fk.ondelete == "CASCADE"
            assert fk.onupdate == "CASCADE"


# ---------------------------------------------------------------------------
# group_exclusions_table
# ---------------------------------------------------------------------------


class TestGroupExclusionsTable:
    """Pin the « banned-user » table.

    Exclusions are how a group admin keeps a previously-removed user
    from rejoining. The contract is intentionally simpler than
    membership (no role) but the unique + cascade rules must match,
    otherwise a delete-and-rejoin loop could bypass the ban.
    """

    def test_tablename(self):
        assert group_exclusions_table.name == "soc_group_exclusions"

    @pytest.mark.parametrize("col_name", ["user_id", "group_id"])
    def test_column_exists(self, col_name):
        assert col_name in group_exclusions_table.columns

    def test_has_exactly_two_columns(self):
        """Exclusions carry no payload — just the (user, group) pair.
        Adding columns here should be a deliberate schema change."""
        assert len(group_exclusions_table.columns) == 2

    def test_no_role_column(self):
        """Exclusions don't have roles — the row's existence IS the
        signal. Catch a copy-paste from `group_members_table`."""
        assert "role" not in group_exclusions_table.columns

    def test_unique_user_group_pair(self):
        """A user can only be excluded from a given group once. The
        unique constraint also acts as a natural key for « is this
        user banned ? » lookups."""
        unique_pairs = {
            tuple(sorted(c.name for c in cons.columns))
            for cons in group_exclusions_table.constraints
            if isinstance(cons, sa.UniqueConstraint)
        }
        assert ("group_id", "user_id") in unique_pairs

    @pytest.mark.parametrize(
        ("col_name", "expected_table"),
        [("user_id", "aut_user"), ("group_id", "soc_group")],
    )
    def test_foreign_keys_target_expected_tables(self, col_name, expected_table):
        col = group_exclusions_table.columns[col_name]
        fk_tables = {fk.column.table.name for fk in col.foreign_keys}
        assert expected_table in fk_tables

    @pytest.mark.parametrize("col_name", ["user_id", "group_id"])
    def test_foreign_keys_cascade_on_delete_and_update(self, col_name):
        """Same rationale as the membership table: avoid orphan rows
        when the referenced user or group disappears."""
        col = group_exclusions_table.columns[col_name]
        for fk in col.foreign_keys:
            assert fk.ondelete == "CASCADE"
            assert fk.onupdate == "CASCADE"
