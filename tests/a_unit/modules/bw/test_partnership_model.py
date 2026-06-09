# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests pinning the *shape* of the `Partnership` SQLAlchemy mapped
class at `app.modules.bw.bw_activation.models.partnership`.

These tests do NOT touch a database. They introspect SQLAlchemy
metadata to lock in :

- Table name (`bw_partnership`) — referenced by Alembic migrations.
- Inheritance from `UUIDAuditBase` — supplies the UUID PK and
  `created_at` / `updated_at` audit columns used by the partnership
  dashboard.
- The full column inventory and nullability — every dashboard query,
  every accept / revoke flow reads these by name.
- The default value of `status` (`INVITED`) — newly invited PR Agency
  partnerships MUST land in `INVITED`, never in `ACTIVE`, otherwise we
  silently grant a partner access without confirmation.
- `partner_bw_id` is a plain `String` column with NO foreign key — this
  is intentional (see the comment in `user_utils.py` line ~529 about
  cross-dialect cast quirks when joining BW IDs across SQLite vs
  PostgreSQL). Pin so a future « let's add the FK » is a deliberate
  decision.
- ON DELETE CASCADE on `business_wall_id` — deleting a BW must clean
  up its outgoing partnerships, otherwise dangling rows leak.

The `PartnershipStatus` enum itself is already covered by
`test_role_enums.py` — we do NOT re-test enum values here, only the
column wiring that depends on the enum.

DB-bound behaviour (INSERT-time defaults firing, ondelete cascade
firing for real) belongs in `b_integration` tests, not here.
"""

from __future__ import annotations

from typing import ClassVar

import pytest
from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import String, Text, inspect as sa_inspect

from app.modules.bw.bw_activation.models.partnership import (
    Partnership,
    PartnershipStatus,
)


def _column(model, name):
    """Fetch a column from a mapped class without instantiating a row."""
    return model.__table__.columns[name]


class TestPartnershipClassShape:
    """The class must be a SQLAlchemy mapped class that inherits from
    `UUIDAuditBase`. The parent supplies the UUID `id` primary key and
    the `created_at` / `updated_at` audit columns the partnership
    dashboard relies on for « who invited which agency, and when »."""

    def test_inherits_from_uuid_audit_base(self):
        """Pin the parent so a refactor to a different base catches
        here, not at first INSERT against the live DB."""
        assert issubclass(Partnership, UUIDAuditBase)

    def test_tablename(self):
        """Hard-coded `__tablename__` is referenced by Alembic
        migrations and (potentially) by raw SQL in dashboard widgets
        — renaming it without a migration would silently break
        SELECTs."""
        assert Partnership.__tablename__ == "bw_partnership"

    def test_is_sqlalchemy_mapped(self):
        """`sa_inspect` succeeds only on mapped classes — a defensive
        gate against the class accidentally losing its `Mapped`
        annotations."""
        mapper = sa_inspect(Partnership)
        assert mapper is not None
        assert mapper.class_ is Partnership

    def test_no_custom_table_args(self):
        """At the time of writing there are NO composite unique
        constraints or indexes declared on `Partnership`. Pin the
        absence so adding one (e.g. UNIQUE on
        `(business_wall_id, partner_bw_id)`) is a deliberate change
        — such a constraint would interact with the « re-invite after
        revoke » flow and needs explicit review."""
        assert getattr(Partnership, "__table_args__", None) is None


class TestPartnershipColumns:
    """The column set is the table's contract with the rest of the
    codebase. Pin it explicitly — every accept / reject / revoke
    handler reads at least one of these columns by name."""

    EXPECTED_COLUMNS: ClassVar[set[str]] = {
        # From UUIDAuditBase
        "id",
        "created_at",
        "updated_at",
        # From Partnership itself
        "business_wall_id",
        "partner_bw_id",
        "status",
        "invited_by_user_id",
        "invitation_message",
        "invited_at",
        "accepted_at",
        "rejected_at",
        "revoked_at",
        "contract_start_date",
        "contract_end_date",
        "notes",
    }

    def test_expected_columns_all_present(self):
        """Every name the BW codebase reads must exist. Extras (e.g.
        `sa_orm_sentinel` from advanced-alchemy) are allowed."""
        actual = set(Partnership.__table__.columns.keys())
        missing = self.EXPECTED_COLUMNS - actual
        assert not missing, f"Missing columns on Partnership: {missing}"

    @pytest.mark.parametrize(
        "col_name",
        [
            "business_wall_id",
            "partner_bw_id",
            "invited_by_user_id",
        ],
    )
    def test_core_identity_columns_are_not_nullable(self, col_name):
        """The « who / whom / by-whom » columns must be NOT NULL — a
        partnership row without a target BW, a partner ID, or an
        inviting user is meaningless and would crash dashboards."""
        assert _column(Partnership, col_name).nullable is False

    @pytest.mark.parametrize(
        "col_name",
        [
            "invited_at",
            "accepted_at",
            "rejected_at",
            "revoked_at",
            "contract_start_date",
            "contract_end_date",
        ],
    )
    def test_lifecycle_timestamps_are_nullable(self, col_name):
        """Each lifecycle timestamp is set only when its transition
        happens — they MUST be nullable so a freshly-invited row
        (with only `invited_at` set, or even none) is valid."""
        assert _column(Partnership, col_name).nullable is True


class TestPartnerBwIdIsString:
    """`partner_bw_id` is intentionally a plain `String` column with
    NO foreign key constraint. The source comment explicitly calls
    this out, and `user_utils.py` (~line 529) documents cross-dialect
    cast quirks (SQLite vs PostgreSQL GUID handling) that motivated
    avoiding the FK. Pin so a future « let's add the FK » is a
    deliberate, reviewed migration."""

    def test_partner_bw_id_type_is_string(self):
        col = _column(Partnership, "partner_bw_id")
        assert isinstance(col.type, String)

    def test_partner_bw_id_has_no_foreign_key(self):
        """The whole point — no FK to `bw_business_wall.id`. If a
        refactor adds one, this test catches it before the migration
        hits production."""
        col = _column(Partnership, "partner_bw_id")
        assert list(col.foreign_keys) == []


class TestStatusDefault:
    """The `status` default is the lynchpin of the partnership flow —
    new rows must land in `INVITED` so the partner has to explicitly
    accept. If a refactor swaps the default to `ACTIVE` or `ACCEPTED`,
    every new invite would silently grant cross-org access without
    partner confirmation."""

    def test_status_default_is_invited_string(self):
        col = _column(Partnership, "status")
        assert col.default is not None
        # ScalarElementColumnDefault exposes the value via .arg
        assert col.default.arg == "invited"

    def test_status_default_equals_enum_invited_value(self):
        """The column default must track the enum — protects against
        a refactor that renames the enum value but forgets to update
        the column default."""
        col = _column(Partnership, "status")
        assert col.default.arg == PartnershipStatus.INVITED.value


class TestForeignKeys:
    """Pin the FK target and ON DELETE behaviour for `business_wall_id`.
    CASCADE is critical : when an organisation deletes its BW, every
    outgoing partnership row must disappear, otherwise the partner
    dashboard would show stale, ghost-BW invitations."""

    def test_business_wall_fk_target(self):
        col = _column(Partnership, "business_wall_id")
        fks = list(col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].column.table.name == "bw_business_wall"
        assert fks[0].column.name == "id"

    def test_business_wall_fk_cascade_on_delete(self):
        col = _column(Partnership, "business_wall_id")
        fk = next(iter(col.foreign_keys))
        assert fk.ondelete == "CASCADE"

    def test_invited_by_user_id_has_no_fk(self):
        """Per the source comment « no FK constraint for POC ». Pin
        so a future « let's add the FK » is a deliberate decision
        — user IDs may already be stale at backfill time."""
        col = _column(Partnership, "invited_by_user_id")
        assert list(col.foreign_keys) == []


class TestTextColumns:
    """`invitation_message` and `notes` are free-form long text — they
    must use `Text`, not `String(N)`, so long invitation pitches and
    multi-paragraph partnership notes don't get silently truncated."""

    @pytest.mark.parametrize("col_name", ["invitation_message", "notes"])
    def test_long_form_columns_use_text(self, col_name):
        col = _column(Partnership, col_name)
        assert isinstance(col.type, Text)

    @pytest.mark.parametrize("col_name", ["invitation_message", "notes"])
    def test_long_form_columns_default_to_empty_string(self, col_name):
        """Defaulting to `""` (not NULL) keeps downstream `.strip()` /
        `.format()` calls safe — no `None` surprises in templates."""
        col = _column(Partnership, col_name)
        assert col.default is not None
        assert col.default.arg == ""


class TestBusinessWallRelationship:
    """The `business_wall` ORM relationship is what the partnership
    dashboard uses to render « invited BY » side. Pin its presence
    and `back_populates` so a refactor doesn't break the bidirectional
    link."""

    def test_business_wall_relationship_exists(self):
        mapper = sa_inspect(Partnership)
        assert "business_wall" in mapper.relationships
        rel = mapper.relationships["business_wall"]
        assert rel.mapper.class_.__name__ == "BusinessWall"

    def test_business_wall_back_populates_partnerships(self):
        """The relationship must round-trip via
        `BusinessWall.partnerships`. If the name drifts, the inverse
        side breaks silently (no error, just no rows on the other
        side)."""
        mapper = sa_inspect(Partnership)
        rel = mapper.relationships["business_wall"]
        assert rel.back_populates == "partnerships"


class TestRepr:
    """The `__repr__` is read in log lines and the debug toolbar. Pin
    its shape so a regression doesn't make grep-by-id useless when
    triaging partnership bugs."""

    def test_repr_contains_id_status_and_partner(self):
        """Build a stand-in (no DB) and assert the format. A small
        duck-typed class is the clearest way to feed `__repr__`."""

        class _StandIn:
            id = "abc-123"
            status = PartnershipStatus.INVITED.value
            partner_bw_id = "partner-xyz"

        rendered = Partnership.__repr__(_StandIn())  # type: ignore[arg-type]
        assert "abc-123" in rendered
        assert "invited" in rendered
        assert "partner-xyz" in rendered
        assert rendered.startswith("<Partnership")
        assert rendered.endswith(">")
