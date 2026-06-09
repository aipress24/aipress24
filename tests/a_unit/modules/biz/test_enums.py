# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the StrEnum dispatch tables in
`app.modules.biz.models._offers`.

The DB column types are `Enum(...)` on Postgres ; their literal values
(`"journalisme"`, `"OPEN"`, `"CDI"`, etc.) are baked into the live
database. Renaming an enum member without an Alembic migration would
fail at COMMIT time with a Postgres-level enum error — a unit test
catches that mistake at decoration time, weeks before it reaches
staging.

Specifically pinned :
- StrEnum member values (case-sensitive — Postgres enums are
  case-sensitive too)
- The expected set of members per enum (no silent drops on refactor)
- Round-tripping a value through the enum (`Enum("journalisme") is
  Enum.JOURNALISME`)
"""

from __future__ import annotations

import pytest

from app.modules.biz.models import (
    ApplicationStatus,
    ContractType,
    MissionCategory,
    MissionStatus,
)


class TestMissionCategory:
    """MissionCategory drives the « Type de mission » select in the
    publish form (#0185). Values are baked into the DB enum + the URL
    query string (`?category=journalisme`)."""

    def test_members_match_spec(self):
        """Erick spec'd exactly three categories ; pin the set."""
        assert {m.value for m in MissionCategory} == {
            "journalisme",
            "communication",
            "innovation",
        }

    def test_values_are_lowercase(self):
        """The URL filter on /biz/?category=… compares lowercase.
        A capital letter slipping in here would silently break the
        Journalism filter sidebar (#0202)."""
        for member in MissionCategory:
            assert member.value == member.value.lower(), (
                f"MissionCategory.{member.name} value must be lowercase"
            )

    @pytest.mark.parametrize(
        "value",
        ["journalisme", "communication", "innovation"],
    )
    def test_round_trip_from_value(self, value):
        """Constructing the enum from its value works — this is the
        common path in the publish form (`MissionCategory(category)`)."""
        assert MissionCategory(value).value == value

    def test_unknown_value_raises(self):
        """Pin the « invalid value » error so a future loose-typing
        regression (e.g. accepting any string) gets caught."""
        with pytest.raises(ValueError, match="totally-bogus"):
            MissionCategory("totally-bogus")


class TestMissionStatus:
    """Lifecycle states of a marketplace offer (mission, project, job).
    The DB column is `missionstatus` ; renaming any member without an
    Alembic migration crashes inserts at COMMIT time."""

    def test_members_match_spec(self):
        """OPEN → FILLED is the « emitter accepted a candidate »
        transition (`mark_filled`). OPEN → CLOSED is the auto-close
        flow (`close_expired_offers`)."""
        names = {m.name for m in MissionStatus}
        assert names == {"OPEN", "FILLED", "CLOSED"}

    def test_values_are_strings(self):
        """StrEnum + auto() yields the lowercased name as the value.
        Pin so a future explicit override doesn't silently change
        the DB-stored values."""
        for member in MissionStatus:
            assert isinstance(member.value, str)
            assert member.value == member.name.lower()


class TestApplicationStatus:
    """Lifecycle of an `OfferApplication` row. PENDING is the initial
    state, SELECTED / REJECTED are the two terminal states reached
    via `update_application_status` (Erick #0199 + #0200)."""

    def test_members_match_spec(self):
        names = {m.name for m in ApplicationStatus}
        assert names == {"PENDING", "SELECTED", "REJECTED"}

    def test_pending_is_initial(self):
        """The `OfferApplication.status` column defaults to PENDING
        (see `_offers.py:222`). Pin the value so the default and the
        enum can't drift out of sync."""
        assert ApplicationStatus.PENDING.value == "pending"


class TestContractType:
    """Job-offer contract types. These map to the
    `PermissionType.INTERNSHIPS / APPRENTICESHIPS / DOCTORAL` checks
    in `jobs_new` — losing any member without updating the check
    silently lets PR managers post unrestricted job offers."""

    def test_members_match_spec(self):
        names = {m.name for m in ContractType}
        assert names == {
            "CDI",
            "CDD",
            "STAGE",
            "APPRENTISSAGE",
            "FREELANCE",
            "DOCTORAL",
        }

    def test_values_are_uppercase(self):
        """ContractType uses explicit string values (not auto()), all
        uppercase, matching what the publish form sends. A regression
        to lowercase would silently break `ContractType(value)` in
        `jobs_new`."""
        for member in ContractType:
            assert member.value == member.value.upper()

    @pytest.mark.parametrize(
        "value",
        ["CDI", "CDD", "STAGE", "APPRENTISSAGE", "FREELANCE", "DOCTORAL"],
    )
    def test_round_trip(self, value):
        assert ContractType(value).value == value

    def test_default_for_new_job_form_is_cdi(self):
        """`jobs_new` reads `form.contract_type.data or ContractType.CDI.value`
        when computing the contract type. Pin CDI's value so the
        default fallback string matches the enum."""
        assert ContractType.CDI.value == "CDI"
