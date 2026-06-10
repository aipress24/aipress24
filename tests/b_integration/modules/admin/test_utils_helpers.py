# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for ``app.modules.admin.utils`` helpers.

These tests live at the b_integration tier because every helper under
test rides the real Flask-SQLAlchemy session: it issues SELECT/UPDATE
statements, flushes new rows, and exercises soft-delete / relationship
mutation logic. There is no pure-logic part that could meaningfully be
exercised at the a_unit tier without re-implementing the persistence
layer. The autouse ``db_session`` fixture wraps each test in a
savepoint that is rolled back on teardown, so we get real DB semantics
without leaking state.

We follow the project rule "no mocks; verify state, not interaction":
each test sets up real model rows, calls the SUT directly, and asserts
on what ended up in (or vanished from) the database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.admin.utils import (
    flush_session,
    gc_all_auto_organisations,
    gc_organisation,
    get_user_per_email,
    merge_organisation,
    remove_user_organisation,
    set_user_organisation,
    set_user_organisation_from_ids,
    toggle_org_active,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _make_user(
    db_session: Session,
    *,
    email: str,
    active: bool = True,
    is_clone: bool = False,
) -> User:
    """Create a persisted active user with an empty KYC profile."""
    user = User(email=email)
    user.active = active
    user.is_clone = is_clone
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_id=f"profile_{user.id}",
        profile_code="TEST",
        profile_label="Test Profile",
        info_professionnelle={},
    )
    db_session.add(profile)
    db_session.flush()
    return user


def _make_org(db_session: Session, name: str = "Test Org") -> Organisation:
    org = Organisation(name=name)
    db_session.add(org)
    db_session.flush()
    return org


class TestGetUserPerEmail:
    """Lookup contract for ``get_user_per_email``."""

    def test_returns_active_user_for_exact_email(self, db_session: Session):
        user = _make_user(db_session, email="alice@example.com")

        found = get_user_per_email("alice@example.com")

        assert found is not None
        assert found.id == user.id

    def test_returns_user_case_insensitively(self, db_session: Session):
        user = _make_user(db_session, email="bob@example.com")

        found = get_user_per_email("BOB@Example.COM")

        assert found is not None
        assert found.id == user.id

    def test_strips_surrounding_whitespace_from_input(self, db_session: Session):
        user = _make_user(db_session, email="carol@example.com")

        found = get_user_per_email("   carol@example.com   ")

        assert found is not None
        assert found.id == user.id

    @pytest.mark.parametrize("bad", ["", "   ", "no-at-sign", "still-no-at  "])
    def test_returns_none_for_invalid_or_blank_email(
        self, db_session: Session, bad: str
    ):
        # A real user exists but the input is malformed, so the helper
        # short-circuits before hitting the DB.
        _make_user(db_session, email="real@example.com")

        assert get_user_per_email(bad) is None

    def test_returns_none_when_email_not_in_db(self, db_session: Session):
        _make_user(db_session, email="present@example.com")

        assert get_user_per_email("missing@example.com") is None

    def test_skips_inactive_user(self, db_session: Session):
        _make_user(db_session, email="inactive@example.com", active=False)

        assert get_user_per_email("inactive@example.com") is None

    def test_skips_clone_user(self, db_session: Session):
        _make_user(db_session, email="clone@example.com", is_clone=True)

        assert get_user_per_email("clone@example.com") is None


class TestSetUserOrganisation:
    """``set_user_organisation`` mutates user.organisation_id + KYC."""

    def test_assigns_org_to_user_and_returns_no_error(self, db_session: Session):
        user = _make_user(db_session, email="member@example.com")
        org = _make_org(db_session, name="Acme")

        error = set_user_organisation(user, org)

        assert error == ""
        refreshed = db_session.get(User, user.id)
        assert refreshed.organisation_id == org.id

    def test_writes_org_name_into_kyc_profile(self, db_session: Session):
        user = _make_user(db_session, email="kyc@example.com")
        org = _make_org(db_session, name="KYC Co")

        set_user_organisation(user, org)

        refreshed = db_session.get(User, user.id)
        # No bw_active set -> falls through to nom_orga
        assert refreshed.profile.info_professionnelle.get("nom_orga") == "KYC Co"

    def test_marks_user_modified_timestamp(self, db_session: Session):
        user = _make_user(db_session, email="touch@example.com")
        org = _make_org(db_session, name="TouchOrg")

        set_user_organisation(user, org)

        refreshed = db_session.get(User, user.id)
        assert refreshed.modified_at is not None
        assert refreshed.validated_at is not None
        assert refreshed.validation_status != ""

    def test_set_user_organisation_from_ids_works_the_same(self, db_session: Session):
        user = _make_user(db_session, email="ids@example.com")
        org = _make_org(db_session, name="ById")

        error = set_user_organisation_from_ids(user.id, org.id)

        assert error == ""
        refreshed = db_session.get(User, user.id)
        assert refreshed.organisation_id == org.id


class TestRemoveUserOrganisation:
    """``remove_user_organisation`` detaches user from its org."""

    def test_clears_organisation_id(self, db_session: Session):
        user = _make_user(db_session, email="leaver@example.com")
        org = _make_org(db_session, name="OldOrg")
        set_user_organisation(user, org)
        assert user.organisation_id == org.id
        # Ensure the relationship is loaded before remove (which reads
        # ``user.organisation`` to decide whether to act).
        db_session.refresh(user)
        assert user.organisation is not None

        error = remove_user_organisation(user)

        assert error == ""
        refreshed = db_session.get(User, user.id)
        assert refreshed.organisation_id is None

    def test_clears_kyc_org_name_fields(self, db_session: Session):
        user = _make_user(db_session, email="kyc-leave@example.com")
        org = _make_org(db_session, name="ToErase")
        set_user_organisation(user, org)

        remove_user_organisation(user)

        refreshed = db_session.get(User, user.id)
        info = refreshed.profile.info_professionnelle
        assert info.get("nom_orga", "") == ""
        assert info.get("nom_media", []) == []

    def test_is_idempotent_for_user_without_organisation(self, db_session: Session):
        # User never belonged to an org; removing should be a no-op
        # error-wise (no IntegrityError, no exception).
        user = _make_user(db_session, email="solo@example.com")

        error = remove_user_organisation(user)

        assert error == ""
        refreshed = db_session.get(User, user.id)
        assert refreshed.organisation_id is None


class TestGcOrganisation:
    """``gc_organisation`` deletes empty AUTO organisations."""

    def test_deletes_empty_auto_org(self, db_session: Session):
        org = _make_org(db_session, name="Empty Auto")
        org_id = org.id

        deleted = gc_organisation(org)

        assert deleted is True
        flush_session(db_session)
        # Either hard-deleted or soft-deleted; in both cases the row is
        # no longer a live, non-deleted organisation.
        survivor = (
            db_session.query(Organisation)
            .filter(Organisation.id == org_id, Organisation.deleted_at.is_(None))
            .first()
        )
        assert survivor is None

    def test_returns_false_for_none(self, db_session: Session):
        assert gc_organisation(None) is False

    def test_skips_org_with_members(self, db_session: Session):
        org = _make_org(db_session, name="Populated")
        user = _make_user(db_session, email="resident@example.com")
        user.organisation_id = org.id
        db_session.flush()

        deleted = gc_organisation(org)

        assert deleted is False
        refreshed = db_session.get(Organisation, org.id)
        assert refreshed is not None
        assert refreshed.deleted_at is None


class TestGcAllAutoOrganisations:
    """``gc_all_auto_organisations`` sweeps the whole table."""

    def test_returns_zero_when_nothing_to_clean(self, db_session: Session):
        # Single org with a member -> not eligible.
        org = _make_org(db_session, name="Has Member")
        user = _make_user(db_session, email="anchor@example.com")
        user.organisation_id = org.id
        db_session.flush()

        assert gc_all_auto_organisations() == 0

    def test_collects_only_eligible_orgs(self, db_session: Session):
        empty1 = _make_org(db_session, name="Empty 1")
        empty2 = _make_org(db_session, name="Empty 2")
        kept = _make_org(db_session, name="Kept")
        user = _make_user(db_session, email="keeper@example.com")
        user.organisation_id = kept.id
        db_session.flush()

        count = gc_all_auto_organisations()

        assert count == 2
        # The "Kept" org with a member must survive.
        survivor = db_session.get(Organisation, kept.id)
        assert survivor is not None
        assert survivor.deleted_at is None
        # The two empty orgs must no longer be visible as live rows.
        for org_id in (empty1.id, empty2.id):
            live = (
                db_session.query(Organisation)
                .filter(
                    Organisation.id == org_id,
                    Organisation.deleted_at.is_(None),
                )
                .first()
            )
            assert live is None

    def test_is_idempotent_when_run_twice(self, db_session: Session):
        _make_org(db_session, name="To Reap")

        first = gc_all_auto_organisations()
        second = gc_all_auto_organisations()

        assert first == 1
        assert second == 0


class TestToggleOrgActiveAndMerge:
    """``toggle_org_active`` and ``merge_organisation`` round-trip."""

    def test_toggle_flips_active_flag(self, db_session: Session):
        org = _make_org(db_session, name="Toggle Me")
        assert org.active is True

        toggle_org_active(org)
        first = db_session.get(Organisation, org.id)
        assert first.active is False

        toggle_org_active(first)
        second = db_session.get(Organisation, org.id)
        assert second.active is True

    def test_merge_persists_attribute_changes(self, db_session: Session):
        org = _make_org(db_session, name="Original")
        org.name = "Renamed"

        merge_organisation(org)

        refreshed = db_session.get(Organisation, org.id)
        assert refreshed.name == "Renamed"
