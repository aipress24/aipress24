# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Round-trip integration tests for ``app.modules.kyc.populate_profile``.

The existing ``tests/a_unit/modules/kyc/test_populate_profile.py`` covers the
pure-Python contract of ``populate_json_field`` and ``populate_form_data``
(default keys, value overrides, unknown-key filtering). This file lives at the
``b_integration`` tier and exercises what the unit suite cannot:

* the dicts returned by ``populate_json_field`` are actually persisted into
  the JSON columns of a real ``KYCProfile`` row and survive a flush + expire +
  reload cycle (the JSON serializer / deserializer is in the loop);
* re-populating the same profile with new form data is idempotent at the
  row-count level — we update one row, we never insert a duplicate child;
* ``populate_form_data`` round-trips the persisted JSON back into a flat
  form-data dict in the shape that the KYC views feed to WTForms.

These guarantees can only be tested against a real SQLAlchemy session, so they
belong here rather than in ``a_unit``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from app.enums import ContactTypeEnum
from app.models.auth import KYCProfile, User
from app.modules.kyc.populate_profile import (
    populate_form_data,
    populate_json_field,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _make_user(db_session: Session, email: str) -> User:
    user = User(email=email, first_name="Test", last_name="User")
    db_session.add(user)
    db_session.flush()
    return user


def _make_profile(db_session: Session, user: User) -> KYCProfile:
    profile = KYCProfile(
        user_id=user.id,
        profile_code="PM_DIR",
        profile_label="Test",
    )
    db_session.add(profile)
    db_session.flush()
    return profile


CATEGORIES = (
    "show_contact_details",
    "info_personnelle",
    "info_professionnelle",
    "match_making",
    "info_hobby",
    "business_wall",
)


class TestPopulateJsonFieldRoundTrip:
    """``populate_json_field`` output survives a real flush + reload cycle."""

    def test_info_personnelle_persists_and_reloads(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session, "perso@example.com")
        profile = _make_profile(db_session, user)

        form_results = {
            "pseudo": "round_tripper",
            "langues": ["fr", "en"],
            "competences": ["seo", "data"],
            "unknown_key_should_be_dropped": "ignored",
        }
        profile.info_personnelle = populate_json_field(
            "info_personnelle", form_results
        )
        db_session.flush()
        db_session.expire(profile)

        reloaded = db_session.get(KYCProfile, profile.id)
        assert reloaded is not None
        assert reloaded.info_personnelle["pseudo"] == "round_tripper"
        assert reloaded.info_personnelle["langues"] == ["fr", "en"]
        assert reloaded.info_personnelle["competences"] == ["seo", "data"]
        # Default keys still present even though they weren't in the form
        assert reloaded.info_personnelle["formations"] == ""
        assert reloaded.info_personnelle["metier"] == []
        # Unknown keys were filtered out by populate_json_field
        assert "unknown_key_should_be_dropped" not in reloaded.info_personnelle

    def test_business_wall_booleans_persist_as_booleans(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session, "bw@example.com")
        profile = _make_profile(db_session, user)

        profile.business_wall = populate_json_field(
            "business_wall",
            {"trigger_media_media": True, "trigger_expert": True},
        )
        db_session.flush()
        db_session.expire(profile)

        reloaded = db_session.get(KYCProfile, profile.id)
        assert reloaded is not None
        assert reloaded.business_wall["trigger_media_media"] is True
        assert reloaded.business_wall["trigger_expert"] is True
        assert reloaded.business_wall["trigger_pr"] is False

    def test_show_contact_details_covers_all_contact_types(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session, "contact@example.com")
        profile = _make_profile(db_session, user)

        profile.show_contact_details = populate_json_field(
            "show_contact_details", {}
        )
        db_session.flush()
        db_session.expire(profile)

        reloaded = db_session.get(KYCProfile, profile.id)
        assert reloaded is not None
        for contact_type in ContactTypeEnum:
            assert f"email_{contact_type.name}" in reloaded.show_contact_details
            assert f"mobile_{contact_type.name}" in reloaded.show_contact_details
            assert reloaded.show_contact_details[
                f"email_{contact_type.name}"
            ] is False

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_empty_form_seeds_default_shape(
        self, db_session: Session, category: str
    ) -> None:
        """Every category seeds the expected default shape, persisted as-is."""
        user = _make_user(db_session, f"{category}@example.com")
        profile = _make_profile(db_session, user)

        populated = populate_json_field(category, {})
        setattr(profile, category, populated)
        db_session.flush()
        db_session.expire(profile)

        reloaded = db_session.get(KYCProfile, profile.id)
        assert reloaded is not None
        stored = getattr(reloaded, category)
        # The JSON-typed column round-trips the dict shape unchanged.
        assert stored == populated
        # And we still have a non-empty default scaffold.
        assert len(stored) > 0


class TestRepopulationIdempotency:
    """Repopulating an existing profile updates in place — no duplicate rows."""

    def test_second_populate_does_not_create_new_profile_row(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session, "idem@example.com")
        profile = _make_profile(db_session, user)
        assert db_session.query(KYCProfile).count() == 1

        # First populate
        profile.info_personnelle = populate_json_field(
            "info_personnelle", {"pseudo": "first"}
        )
        db_session.flush()
        assert db_session.query(KYCProfile).count() == 1

        # Second populate with overlapping + new fields — same row updated.
        profile.info_personnelle = populate_json_field(
            "info_personnelle",
            {"pseudo": "second", "langues": ["fr"]},
        )
        db_session.flush()
        db_session.expire(profile)

        assert db_session.query(KYCProfile).count() == 1
        reloaded = db_session.get(KYCProfile, profile.id)
        assert reloaded is not None
        assert reloaded.info_personnelle["pseudo"] == "second"
        assert reloaded.info_personnelle["langues"] == ["fr"]

    def test_repopulate_resets_to_defaults_for_missing_keys(
        self, db_session: Session
    ) -> None:
        """populate_json_field is a replace, not a merge — missing keys reset."""
        user = _make_user(db_session, "reset@example.com")
        profile = _make_profile(db_session, user)

        profile.info_personnelle = populate_json_field(
            "info_personnelle",
            {"pseudo": "filled", "langues": ["fr", "en"]},
        )
        db_session.flush()

        # Second call without 'langues' — the contract is "replace with new
        # defaults overlaid by content", so langues goes back to [].
        profile.info_personnelle = populate_json_field(
            "info_personnelle", {"pseudo": "still_filled"}
        )
        db_session.flush()
        db_session.expire(profile)

        reloaded = db_session.get(KYCProfile, profile.id)
        assert reloaded is not None
        assert reloaded.info_personnelle["pseudo"] == "still_filled"
        assert reloaded.info_personnelle["langues"] == []


class TestFormDataReverseRoundTrip:
    """``populate_form_data`` reads a persisted profile back into a flat dict.

    This mirrors the KYC edit view: it loads a profile, then builds the
    WTForms-ready ``data`` dict by overlaying each persisted JSON column on the
    category's defaults.
    """

    def test_persisted_profile_round_trips_into_form_data(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session, "form@example.com")
        profile = _make_profile(db_session, user)

        # Persist a partial info_personnelle.
        profile.info_personnelle = populate_json_field(
            "info_personnelle",
            {"pseudo": "round", "competences": ["seo"]},
        )
        db_session.flush()
        db_session.expire(profile)

        reloaded = db_session.get(KYCProfile, profile.id)
        assert reloaded is not None

        # Now play the view-layer role: build the form data dict from the
        # persisted JSON.
        form_data: dict[str, Any] = {}
        populate_form_data(
            "info_personnelle", reloaded.info_personnelle, form_data
        )

        assert form_data["pseudo"] == "round"
        assert form_data["competences"] == ["seo"]
        # Default-filled keys for missing fields
        assert form_data["formations"] == ""
        assert form_data["langues"] == []

    def test_form_data_does_not_clobber_unrelated_keys(
        self, db_session: Session
    ) -> None:
        """The view layer composes multiple categories into one dict — verify
        that ``populate_form_data`` only writes keys it owns."""
        user = _make_user(db_session, "compose@example.com")
        profile = _make_profile(db_session, user)

        profile.info_personnelle = populate_json_field(
            "info_personnelle", {"pseudo": "owner"}
        )
        profile.info_hobby = populate_json_field(
            "info_hobby", {"hobbies": "chess"}
        )
        db_session.flush()
        db_session.expire(profile)

        reloaded = db_session.get(KYCProfile, profile.id)
        assert reloaded is not None

        form_data: dict[str, Any] = {"csrf_token": "kept", "submit": "kept"}
        populate_form_data(
            "info_personnelle", reloaded.info_personnelle, form_data
        )
        populate_form_data("info_hobby", reloaded.info_hobby, form_data)

        # Both categories ended up in the same dict, alongside pre-existing
        # control keys.
        assert form_data["pseudo"] == "owner"
        assert form_data["hobbies"] == "chess"
        assert form_data["csrf_token"] == "kept"
        assert form_data["submit"] == "kept"


class TestInvalidCategory:
    """Misuse at the boundary still raises — even with a real DB attached."""

    @pytest.mark.parametrize(
        "bad_category", ["", "unknown", "INFO_PERSONNELLE", "info-personnelle"]
    )
    def test_populate_json_field_rejects_unknown_category(
        self, db_session: Session, bad_category: str
    ) -> None:
        user = _make_user(db_session, f"bad-{bad_category or 'empty'}@x.io")
        _make_profile(db_session, user)

        with pytest.raises(ValueError, match="Unknow category"):
            populate_json_field(bad_category, {})

    def test_populate_form_data_rejects_unknown_category(
        self, db_session: Session
    ) -> None:
        user = _make_user(db_session, "bad-form@example.com")
        _make_profile(db_session, user)

        with pytest.raises(ValueError, match="Unknow category"):
            populate_form_data("not_a_real_category", {}, {})
