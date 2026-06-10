# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Round-trip integration tests for ``app.modules.kyc.organisation_utils``.

These exercises pin down the DB-touching contracts of the KYC organisation
helpers using the real SQLAlchemy session (via the autouse ``db_session``
fixture) rather than any in-memory or mocked substitute. They assert on:

* the family-filter queries (``get_organisation_family`` and the three
  ``get_organisation_for_noms_*`` aggregations) by seeding rows with
  diverse ``bw_active`` / ``bw_id`` combinations and checking the names
  returned in the right order,
* the lookup-or-create contract of ``store_auto_organisation`` —
  including normalisation (strip), the empty-name short-circuit, and the
  rule that an existing non-AUTO row with the same name does not block
  a new AUTO row from being created,
* the email-keyed resolution of ``find_inviting_organisations``,
  including case-insensitivity and the orphan-id tolerance documented
  in the source (no FK on ``Invitation.organisation_id``).

Lives at the ``b_integration`` tier: nothing here is pure logic — every
test goes through a real ``Session`` round-trip.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.kyc.organisation_utils import (
    find_inviting_organisations,
    get_organisation_family,
    get_organisation_for_noms_com,
    get_organisation_for_noms_medias,
    get_organisation_for_noms_orgas,
    store_auto_organisation,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _bw_org(name: str, bw_active: str) -> Organisation:
    """Build a non-AUTO Organisation row (has a ``bw_id``)."""
    return Organisation(name=name, bw_active=bw_active, bw_id=uuid4())


def _auto_org(name: str) -> Organisation:
    """Build an AUTO Organisation row (no ``bw_id``)."""
    return Organisation(name=name)


class TestGetOrganisationFamily:
    """``get_organisation_family`` filters by ``bw_active`` or AUTO."""

    def test_none_returns_only_auto_orgs_sorted(
        self, db_session: Session
    ) -> None:
        db_session.add_all(
            [
                _auto_org("Zeta Auto"),
                _auto_org("Alpha Auto"),
                _bw_org("Media Org", "media"),
            ]
        )
        db_session.flush()

        names = get_organisation_family(None)

        assert names == ["Alpha Auto", "Zeta Auto"]

    @pytest.mark.parametrize(
        "bw_type",
        ["media", "pr", "academics", "transformers"],
    )
    def test_filters_by_bw_active(
        self, db_session: Session, bw_type: str
    ) -> None:
        db_session.add_all(
            [
                _bw_org("Match Org", bw_type),
                _bw_org("Other Org", "leaders_experts"),
                _auto_org("Auto Org"),
            ]
        )
        db_session.flush()

        names = get_organisation_family(bw_type)

        if bw_type == "leaders_experts":
            assert set(names) == {"Match Org", "Other Org"}
        else:
            assert names == ["Match Org"]

    def test_empty_db_returns_empty_list(self, db_session: Session) -> None:
        assert get_organisation_family(None) == []
        assert get_organisation_family("media") == []


class TestGetOrganisationForNomsMedias:
    """media + AUTO orgs surface; non-media BW orgs are filtered out."""

    def test_returns_media_and_auto_excludes_pr(
        self, db_session: Session
    ) -> None:
        db_session.add_all(
            [
                _bw_org("Media Org", "media"),
                _bw_org("PR Org", "pr"),
                _auto_org("Auto Org"),
                _bw_org("Academics Org", "academics"),
            ]
        )
        db_session.flush()

        names = get_organisation_for_noms_medias()

        assert "Media Org" in names
        assert "Auto Org" in names
        assert "PR Org" not in names
        assert "Academics Org" not in names

    def test_results_sorted_by_name(self, db_session: Session) -> None:
        db_session.add_all(
            [
                _auto_org("Zeta"),
                _bw_org("Alpha", "media"),
                _auto_org("Mike"),
            ]
        )
        db_session.flush()

        names = get_organisation_for_noms_medias()

        assert names == ["Alpha", "Mike", "Zeta"]


class TestGetOrganisationForNomsOrgas:
    """The ``OTHER`` family aggregation excludes media and pr."""

    def test_excludes_media_and_pr_includes_others_and_auto(
        self, db_session: Session
    ) -> None:
        db_session.add_all(
            [
                _bw_org("Media Org", "media"),
                _bw_org("PR Org", "pr"),
                _bw_org("Micro Org", "micro"),
                _bw_org("Academics Org", "academics"),
                _bw_org("Union Org", "union"),
                _bw_org("Transformers Org", "transformers"),
                _bw_org("Leaders Org", "leaders_experts"),
                _bw_org("Corp Media Org", "corporate_media"),
                _auto_org("Auto Org"),
            ]
        )
        db_session.flush()

        names = get_organisation_for_noms_orgas()

        assert "Media Org" not in names
        assert "PR Org" not in names
        for expected in (
            "Micro Org",
            "Academics Org",
            "Union Org",
            "Transformers Org",
            "Leaders Org",
            "Corp Media Org",
            "Auto Org",
        ):
            assert expected in names


class TestGetOrganisationForNomsCom:
    """COM family = ``bw_active == 'pr'`` + AUTO."""

    def test_returns_pr_and_auto_excludes_media(
        self, db_session: Session
    ) -> None:
        db_session.add_all(
            [
                _bw_org("Media Org", "media"),
                _bw_org("PR Org", "pr"),
                _auto_org("Auto Org"),
            ]
        )
        db_session.flush()

        names = get_organisation_for_noms_com()

        assert "PR Org" in names
        assert "Auto Org" in names
        assert "Media Org" not in names


class TestStoreAutoOrganisationCreatesRow:
    """``store_auto_organisation`` persists a fresh AUTO row when none exists."""

    def test_creates_new_auto_row(self, db_session: Session) -> None:
        result = store_auto_organisation(user=None, org_name="Fresh AUTO")  # type: ignore[arg-type]

        assert result is not None
        assert result.id is not None
        assert result.name == "Fresh AUTO"
        assert result.is_auto is True
        assert result.bw_id is None
        # The row was persisted in the test session.
        assert db_session.query(Organisation).count() == 1

    def test_normalises_whitespace(self, db_session: Session) -> None:
        result = store_auto_organisation(
            user=None,  # type: ignore[arg-type]
            org_name="  Padded Org  ",
        )

        assert result is not None
        assert result.name == "Padded Org"

    @pytest.mark.parametrize("bad_name", ["", "   ", "\t\n"])
    def test_blank_name_returns_none_and_creates_nothing(
        self, db_session: Session, bad_name: str
    ) -> None:
        result = store_auto_organisation(
            user=None,  # type: ignore[arg-type]
            org_name=bad_name,
        )

        assert result is None
        assert db_session.query(Organisation).count() == 0


class TestStoreAutoOrganisationIdempotency:
    """Existing AUTO rows are returned; existing non-AUTO rows do not block."""

    def test_returns_existing_auto_row(self, db_session: Session) -> None:
        existing = _auto_org("Existing Auto")
        db_session.add(existing)
        db_session.flush()

        result = store_auto_organisation(
            user=None,  # type: ignore[arg-type]
            org_name="Existing Auto",
        )

        assert result is not None
        assert result.id == existing.id
        assert db_session.query(Organisation).count() == 1

    def test_creates_auto_when_only_bw_org_with_same_name_exists(
        self, db_session: Session
    ) -> None:
        bw_row = _bw_org("Dual Name", "media")
        db_session.add(bw_row)
        db_session.flush()

        result = store_auto_organisation(
            user=None,  # type: ignore[arg-type]
            org_name="Dual Name",
        )

        assert result is not None
        assert result.id != bw_row.id
        assert result.is_auto
        # Two rows now share the name: one BW-backed, one AUTO.
        assert db_session.query(Organisation).count() == 2


class TestFindInvitingOrganisations:
    """``find_inviting_organisations`` resolves orgs by invitation email."""

    def test_returns_org_for_matching_invitation(
        self, db_session: Session
    ) -> None:
        org = _bw_org("Inviting Org", "media")
        db_session.add(org)
        db_session.flush()
        db_session.add(
            Invitation(email="invited@example.com", organisation_id=org.id)
        )
        db_session.flush()

        result = find_inviting_organisations("invited@example.com")

        assert [o.id for o in result] == [org.id]

    def test_case_insensitive_email_match(self, db_session: Session) -> None:
        org = _bw_org("Case Org", "media")
        db_session.add(org)
        db_session.flush()
        db_session.add(
            Invitation(email="MixedCase@Example.com", organisation_id=org.id)
        )
        db_session.flush()

        result = find_inviting_organisations("mixedcase@example.com")

        assert [o.id for o in result] == [org.id]

    @pytest.mark.parametrize("bad_email", ["", "no-at-sign", "   "])
    def test_invalid_email_returns_empty_list(
        self, db_session: Session, bad_email: str
    ) -> None:
        assert find_inviting_organisations(bad_email) == []

    def test_returns_empty_when_no_invitation(
        self, db_session: Session
    ) -> None:
        org = _bw_org("Unrelated", "media")
        db_session.add(org)
        db_session.flush()

        assert find_inviting_organisations("nobody@example.com") == []

    def test_orphan_invitation_id_is_skipped(
        self, db_session: Session
    ) -> None:
        """Audit L2 invariant: dead organisation_id does not raise."""
        org = _bw_org("Live Org", "media")
        db_session.add(org)
        db_session.flush()
        db_session.add_all(
            [
                Invitation(email="dual@example.com", organisation_id=org.id),
                # 10**12 is an id no Organisation row will ever have here.
                Invitation(email="dual@example.com", organisation_id=10**12),
            ]
        )
        db_session.flush()

        result = find_inviting_organisations("dual@example.com")

        # The orphan invitation is silently skipped, not raised.
        assert [o.id for o in result] == [org.id]

    def test_multiple_orgs_invite_same_email(
        self, db_session: Session
    ) -> None:
        org_a = _bw_org("Org A", "media")
        org_b = _bw_org("Org B", "pr")
        db_session.add_all([org_a, org_b])
        db_session.flush()
        db_session.add_all(
            [
                Invitation(email="multi@example.com", organisation_id=org_a.id),
                Invitation(email="multi@example.com", organisation_id=org_b.id),
            ]
        )
        db_session.flush()

        result = find_inviting_organisations("multi@example.com")

        assert {o.id for o in result} == {org_a.id, org_b.id}
