# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for pure helpers on ``app.models.auth``.

The auth module concentrates a lot of "pure on a User/KYCProfile
instance" logic — name building, role checks, KYC list views, photo
URL fall-backs, BW selection. Most of these don't need persistence,
they only read attributes set on the instance.

This file exercises those helpers by instantiating ``User``,
``KYCProfile``, ``Role`` and ``Organisation`` in memory and never
flushing. The ``db`` fixture is still requested to guarantee an app
context (the SQLAlchemy registry must be initialised before the
mapped classes can be instantiated) but no commit / flush is needed
since every helper here is pure-Python over instance attributes.

Tests check real state (return values, mutated ``roles`` list) and
never spy on calls — per the project rule "verify state, not
interaction".
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest

from app.enums import ContactTypeEnum, RoleEnum
from app.models.auth import (
    KYCProfile,
    Role,
    User,
    clone_kycprofile,
    clone_user,
    merge_values_from_other_user,
)
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


def _make_user(**kw: Any) -> User:
    """Build a ``User`` without going through SQLAlchemy session.

    ``__init__`` only generates ``fs_uniquifier`` if missing.
    """
    return User(**kw)


def _make_profile(**kw: Any) -> KYCProfile:
    """Build a ``KYCProfile`` with sane in-memory defaults.

    SQLAlchemy mapped-column defaults only fire at flush time, so a
    freshly-constructed in-memory profile has ``info_* == None``. The
    helpers under test all use ``.get(...)``, which assumes a ``dict``,
    so we pre-fill the JSON columns with ``{}`` unless the caller
    overrides them.
    """
    defaults: dict[str, Any] = {
        "show_contact_details": {},
        "info_personnelle": {},
        "info_professionnelle": {},
        "match_making": {},
        "info_hobby": {},
        "business_wall": {},
    }
    defaults.update(kw)
    return KYCProfile(**defaults)


class TestFullName:
    """``User.full_name`` and the ``name`` alias."""

    @pytest.mark.parametrize(
        ("first", "last", "expected"),
        [
            ("Ada", "Lovelace", "Ada Lovelace"),
            ("", "Lovelace", " Lovelace"),
            ("Ada", "", "Ada "),
            ("", "", " "),
            ("Jean-Luc", "Picard", "Jean-Luc Picard"),
        ],
    )
    def test_full_name_concatenates_first_last(
        self,
        db: SQLAlchemy,
        first: str,
        last: str,
        expected: str,
    ) -> None:
        user = _make_user(first_name=first, last_name=last)
        assert user.full_name == expected

    def test_name_is_alias_of_full_name(self, db: SQLAlchemy) -> None:
        user = _make_user(first_name="Grace", last_name="Hopper")
        assert user.name == user.full_name == "Grace Hopper"


class TestRepr:
    """``User.__repr__`` is a debug helper — covers the e-mail in
    the rendering."""

    def test_repr_contains_email(self, db: SQLAlchemy) -> None:
        user = _make_user(email="alan@example.com")
        assert repr(user) == "<User alan@example.com>"

    def test_repr_with_no_email_still_renders(self, db: SQLAlchemy) -> None:
        user = _make_user()
        # email defaults to None on a fresh instance.
        assert "User" in repr(user)


class TestFsUniquifier:
    """``__init__`` must auto-fill ``fs_uniquifier`` when missing —
    Flask-Security requires it to be present on every user row."""

    def test_init_fills_uniquifier(self, db: SQLAlchemy) -> None:
        user = _make_user()
        assert user.fs_uniquifier
        # Must be a valid hex UUID.
        uuid.UUID(hex=user.fs_uniquifier)

    def test_init_keeps_provided_uniquifier(self, db: SQLAlchemy) -> None:
        fixed = "0123456789abcdef0123456789abcdef"
        user = _make_user(fs_uniquifier=fixed)
        assert user.fs_uniquifier == fixed

    def test_two_users_get_distinct_uniquifiers(self, db: SQLAlchemy) -> None:
        a = _make_user()
        b = _make_user()
        assert a.fs_uniquifier != b.fs_uniquifier


class TestJobTitleProxy:
    """``User.job_title`` reads through ``profile.profile_label`` and
    must degrade to ``""`` when no profile is attached."""

    def test_returns_empty_when_profile_is_none(self, db: SQLAlchemy) -> None:
        user = _make_user()
        # No profile assigned — relationship is None.
        assert user.job_title == ""

    def test_returns_profile_label(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.profile = _make_profile(profile_label="Senior Developer")
        assert user.job_title == "Senior Developer"


class TestMetierFonctionProxy:
    """``User.metier_fonction`` proxies the profile, but must not crash
    when the profile is missing (regression hardened in audit L5)."""

    def test_returns_empty_when_profile_is_none(self, db: SQLAlchemy) -> None:
        user = _make_user()
        assert user.metier_fonction == ""

    def test_returns_profile_metier_fonction(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.profile = _make_profile(
            match_making={"fonctions_journalisme": ["Rédacteur en chef"]},
        )
        assert user.metier_fonction == "Rédacteur en chef"

    def test_falls_through_to_metiers_first(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.profile = _make_profile(
            info_personnelle={"metier_principal_detail": ["expert sécurité"]},
        )
        assert user.metier_fonction == "expert sécurité"


class TestMetiersAndTousMetiers:
    """``User.metiers`` and ``User.tous_metiers`` aggregate the
    profile's two metier sources."""

    def test_metiers_returns_principal(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.profile = _make_profile(
            info_personnelle={"metier_principal_detail": ["A", "B"]},
        )
        assert user.metiers == ["A", "B"]

    def test_tous_metiers_unions_principal_and_autres(
        self, db: SQLAlchemy
    ) -> None:
        user = _make_user()
        user.profile = _make_profile(
            info_personnelle={
                "metier_principal_detail": ["A", "B"],
                "metier_detail": ["B", "C"],
            },
        )
        assert user.tous_metiers == {"A", "B", "C"}

    def test_tous_metiers_with_empty_lists(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.profile = _make_profile()
        assert user.tous_metiers == set()


class TestOrganisationName:
    """``User.organisation_name`` falls back to ``""`` when no org."""

    def test_empty_without_organisation(self, db: SQLAlchemy) -> None:
        user = _make_user()
        assert user.organisation_name == ""

    def test_returns_org_name(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.organisation = Organisation(name="ACME Corp")
        assert user.organisation_name == "ACME Corp"


class TestHasRoleNoPersist:
    """``has_role`` is pure list scanning over ``self.roles``."""

    def test_role_object_match(self, db: SQLAlchemy) -> None:
        role = Role(name="MANAGER", description="m")
        user = _make_user()
        user.roles = [role]
        assert user.has_role(role) is True

    def test_role_object_miss(self, db: SQLAlchemy) -> None:
        role_a = Role(name="MANAGER", description="m")
        role_b = Role(name="LEADER", description="l")
        user = _make_user()
        user.roles = [role_a]
        # Different Role identity AND different name -> False.
        assert user.has_role(role_b) is False

    def test_role_enum_match(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.roles = [Role(name=RoleEnum.LEADER.name, description="l")]
        assert user.has_role(RoleEnum.LEADER) is True
        assert user.has_role(RoleEnum.MANAGER) is False

    def test_role_string_match(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.roles = [Role(name="EXPERT", description="e")]
        assert user.has_role("EXPERT") is True
        assert user.has_role("LEADER") is False

    @pytest.mark.parametrize("bad", [123, 1.5, None, [], {}])
    def test_invalid_type_raises(self, db: SQLAlchemy, bad: object) -> None:
        user = _make_user()
        user.roles = []
        with pytest.raises(ValueError):
            user.has_role(bad)  # type: ignore[arg-type]


class TestAddAndRemoveRole:
    """``add_role`` is idempotent; ``remove_role`` filters by name and
    must handle the in-memory duplicate state (commit 2f7d18cf)."""

    def test_add_role_returns_true_when_new(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.roles = []
        role = Role(name="MANAGER", description="m")
        assert user.add_role(role) is True
        assert role in user.roles

    def test_add_role_returns_false_when_already_present(
        self, db: SQLAlchemy
    ) -> None:
        user = _make_user()
        role = Role(name="MANAGER", description="m")
        user.roles = [role]
        assert user.add_role(role) is False
        # The list must not have grown.
        assert user.roles.count(role) == 1

    def test_remove_role_by_object(self, db: SQLAlchemy) -> None:
        user = _make_user()
        role = Role(name="MANAGER", description="m")
        user.roles = [role]
        user.remove_role(role)
        assert user.roles == []

    def test_remove_role_by_enum(self, db: SQLAlchemy) -> None:
        user = _make_user()
        role = Role(name=RoleEnum.LEADER.name, description="l")
        user.roles = [role]
        user.remove_role(RoleEnum.LEADER)
        assert user.roles == []

    def test_remove_role_by_string(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.roles = [Role(name="MANAGER", description="m")]
        user.remove_role("MANAGER")
        assert user.roles == []

    def test_remove_role_invalid_type_raises(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.roles = []
        with pytest.raises(ValueError):
            user.remove_role(123)  # type: ignore[arg-type]

    def test_remove_role_handles_inmemory_duplicates(
        self, db: SQLAlchemy
    ) -> None:
        """Pre-2f7d18cf: ``list.remove() + break`` left a lingering
        duplicate. The current implementation rebuilds the list so all
        matches go in one pass.
        """
        user = _make_user()
        role = Role(name="MANAGER", description="m")
        user.roles = [role, role, role]
        user.remove_role(RoleEnum.MANAGER)
        assert user.roles == []


class TestIsLeaderShortcut:
    """``is_leader`` is just sugar for ``has_role(LEADER)``."""

    def test_true_when_role_present(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.roles = [Role(name=RoleEnum.LEADER.name, description="l")]
        assert user.is_leader is True

    def test_false_when_role_absent(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.roles = []
        assert user.is_leader is False


class TestIsMember:
    """``is_member`` compares ``organisation_id`` (no DB join)."""

    def test_false_when_user_has_no_org_id(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.organisation_id = None
        assert user.is_member(42) is False

    def test_true_when_ids_match(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.organisation_id = 42
        assert user.is_member(42) is True

    def test_false_when_ids_differ(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.organisation_id = 42
        assert user.is_member(99) is False


class TestFirstCommunity:
    """Resolves the user's community by precedence order."""

    @pytest.mark.parametrize(
        "role_enum",
        [
            RoleEnum.PRESS_MEDIA,
            RoleEnum.PRESS_RELATIONS,
            RoleEnum.EXPERT,
            RoleEnum.TRANSFORMER,
            RoleEnum.ACADEMIC,
        ],
    )
    def test_single_community_role(
        self, db: SQLAlchemy, role_enum: RoleEnum
    ) -> None:
        user = _make_user()
        user.roles = [Role(name=role_enum.name, description="")]
        assert user.first_community() == role_enum

    def test_precedence_press_media_wins(self, db: SQLAlchemy) -> None:
        """PRESS_MEDIA comes before EXPERT in the precedence tuple."""
        user = _make_user()
        user.roles = [
            Role(name=RoleEnum.EXPERT.name, description=""),
            Role(name=RoleEnum.PRESS_MEDIA.name, description=""),
        ]
        assert user.first_community() == RoleEnum.PRESS_MEDIA

    def test_raises_when_no_community(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.roles = [Role(name=RoleEnum.LEADER.name, description="")]
        with pytest.raises(RuntimeError):
            user.first_community()


class TestCurrentSelectedBwId:
    """The BW the user is acting on — falls back to their own org's BW."""

    def test_returns_none_when_no_selection_and_no_org(
        self, db: SQLAlchemy
    ) -> None:
        user = _make_user()
        user.selected_bw_id = None
        # No org assigned.
        assert user.current_selected_bw_id is None

    def test_returns_own_org_bw_when_no_selection(
        self, db: SQLAlchemy
    ) -> None:
        own = uuid.uuid4()
        user = _make_user()
        user.selected_bw_id = None
        user.organisation = Organisation(name="own", bw_id=own)
        assert user.current_selected_bw_id == own

    def test_returns_explicit_selection(self, db: SQLAlchemy) -> None:
        own = uuid.uuid4()
        other = uuid.uuid4()
        user = _make_user()
        user.selected_bw_id = other
        user.organisation = Organisation(name="own", bw_id=own)
        assert user.current_selected_bw_id == other

    def test_returns_selection_even_without_org(self, db: SQLAlchemy) -> None:
        sel = uuid.uuid4()
        user = _make_user()
        user.selected_bw_id = sel
        assert user.current_selected_bw_id == sel


class TestIsManagingAnotherBw:
    """True if the user picked a BW that is not their own org's BW."""

    def test_false_when_no_selection(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.selected_bw_id = None
        assert user.is_managing_another_bw is False

    def test_false_when_selection_equals_own_bw(self, db: SQLAlchemy) -> None:
        own = uuid.uuid4()
        user = _make_user()
        user.selected_bw_id = own
        user.organisation = Organisation(name="own", bw_id=own)
        assert user.is_managing_another_bw is False

    def test_true_when_selection_differs_from_own(
        self, db: SQLAlchemy
    ) -> None:
        user = _make_user()
        user.selected_bw_id = uuid.uuid4()
        user.organisation = Organisation(name="own", bw_id=uuid.uuid4())
        assert user.is_managing_another_bw is True

    def test_true_when_selection_set_but_no_org(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.selected_bw_id = uuid.uuid4()
        # No organisation: own BW resolves to None, selection != None.
        assert user.is_managing_another_bw is True


class TestImageSignedUrlFallbacks:
    """When the underlying ``FileObject`` is missing, the helpers must
    return the static transparent placeholder rather than raise.

    These cover the early-return branch (``file_obj is None``) — the
    full sign path requires a live S3 backend.
    """

    PLACEHOLDER = "/static/img/transparent-square.png"

    def test_cover_image_url_fallback(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.cover_image = None
        assert user.cover_image_signed_url() == self.PLACEHOLDER

    def test_photo_image_url_fallback(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.photo_image = None
        assert user.photo_image_signed_url() == self.PLACEHOLDER

    def test_photo_carte_presse_url_fallback(self, db: SQLAlchemy) -> None:
        user = _make_user()
        user.photo_carte_presse_image = None
        assert user.photo_carte_presse_image_signed_url() == self.PLACEHOLDER


class TestKYCProfileListAccessors:
    """The KYCProfile exposes a bunch of read-only list views over its
    JSON columns. They are all pure-Python and must default to an empty
    list when the key is missing (a fresh / partially-imported profile
    has ``info_* == {}``).
    """

    def test_metiers_empty_default(self, db: SQLAlchemy) -> None:
        assert _make_profile().metiers == []

    def test_metiers_autres_empty_default(self, db: SQLAlchemy) -> None:
        assert _make_profile().metiers_autres == []

    def test_secteurs_activite_concatenates_three_lists(
        self, db: SQLAlchemy
    ) -> None:
        profile = _make_profile(
            info_professionnelle={
                "secteurs_activite_medias_detail": ["m1"],
                "secteurs_activite_rp_detail": ["r1", "r2"],
                "secteurs_activite_detailles_detail": ["d1"],
            },
        )
        assert profile.secteurs_activite == ["m1", "r1", "r2", "d1"]

    def test_secteurs_activite_empty_default(self, db: SQLAlchemy) -> None:
        assert _make_profile().secteurs_activite == []

    def test_toutes_fonctions_concatenates_four_lists(
        self, db: SQLAlchemy
    ) -> None:
        profile = _make_profile(
            match_making={
                "fonctions_journalisme": ["j"],
                "fonctions_pol_adm_detail": ["p"],
                "fonctions_org_priv_detail": ["o"],
                "fonctions_ass_syn_detail": ["a"],
            },
        )
        assert profile.toutes_fonctions == ["j", "p", "o", "a"]

    @pytest.mark.parametrize(
        ("prop_name", "key"),
        [
            ("fonctions_journalisme", "fonctions_journalisme"),
            ("fonctions_pol_adm_detail", "fonctions_pol_adm_detail"),
            ("fonctions_org_priv_detail", "fonctions_org_priv_detail"),
            ("fonctions_ass_syn_detail", "fonctions_ass_syn_detail"),
        ],
    )
    def test_fonction_props_read_from_match_making(
        self, db: SQLAlchemy, prop_name: str, key: str
    ) -> None:
        profile = _make_profile(match_making={key: ["x"]})
        assert getattr(profile, prop_name) == ["x"]

    @pytest.mark.parametrize(
        ("prop_name", "key"),
        [
            ("type_entreprise_media", "type_entreprise_media"),
            ("type_presse_et_media", "type_presse_et_media"),
            ("type_agence_rp", "type_agence_rp"),
            ("type_organisation", "type_orga_detail"),
            ("taille_organisation", "taille_orga"),
        ],
    )
    def test_type_props_read_from_info_professionnelle(
        self, db: SQLAlchemy, prop_name: str, key: str
    ) -> None:
        profile = _make_profile(info_professionnelle={key: ["v"]})
        assert getattr(profile, prop_name) == ["v"]

    @pytest.mark.parametrize(
        ("prop_name", "key"),
        [
            ("langues", "langues"),
            ("competences", "competences"),
            ("competences_journalisme", "competences_journalisme"),
        ],
    )
    def test_personnelle_list_props(
        self, db: SQLAlchemy, prop_name: str, key: str
    ) -> None:
        profile = _make_profile(info_personnelle={key: ["v"]})
        assert getattr(profile, prop_name) == ["v"]

    def test_transformations_majeures(self, db: SQLAlchemy) -> None:
        profile = _make_profile(
            match_making={"transformation_majeure_detail": ["t1", "t2"]},
        )
        assert profile.transformations_majeures == ["t1", "t2"]

    def test_list_props_empty_when_dicts_empty(self, db: SQLAlchemy) -> None:
        """Comprehensive baseline: every list view returns ``[]`` on a
        fresh profile, exercising the ``.get(..., [])`` branch."""
        profile = _make_profile()
        for attr in [
            "fonctions_journalisme",
            "fonctions_pol_adm_detail",
            "fonctions_org_priv_detail",
            "fonctions_ass_syn_detail",
            "type_entreprise_media",
            "type_presse_et_media",
            "type_agence_rp",
            "langues",
            "competences",
            "competences_journalisme",
            "type_organisation",
            "taille_organisation",
            "transformations_majeures",
            "toutes_fonctions",
        ]:
            assert getattr(profile, attr) == [], attr


class TestKYCProfileVilleParsing:
    """``ville`` parses ``pays_zip_ville_detail`` and handles list-typed
    input (legacy multi-select form) plus missing-key / short-string."""

    def test_ville_empty_when_key_missing(self, db: SQLAlchemy) -> None:
        profile = _make_profile()
        assert profile.ville == ""

    def test_ville_from_string(self, db: SQLAlchemy) -> None:
        profile = _make_profile(
            info_professionnelle={"pays_zip_ville_detail": "FRA / 75001 Paris"},
        )
        assert profile.ville == "Paris"

    def test_ville_from_list(self, db: SQLAlchemy) -> None:
        profile = _make_profile(
            info_professionnelle={
                "pays_zip_ville_detail": [
                    "FRA / 69001 Lyon",
                    "FRA / 75001 Paris",
                ],
            },
        )
        # Only the first entry is parsed.
        assert profile.ville == "Lyon"

    def test_ville_empty_when_string_too_short(self, db: SQLAlchemy) -> None:
        profile = _make_profile(
            info_professionnelle={"pays_zip_ville_detail": "FRA"},
        )
        assert profile.ville == ""


class TestKYCProfileGetFirstValue:
    """``get_first_value`` collapses lists to their first element."""

    def test_string_passthrough(self, db: SQLAlchemy) -> None:
        profile = _make_profile(info_professionnelle={"nom_media": "Le Monde"})
        assert profile.get_first_value("nom_media") == "Le Monde"

    def test_list_first(self, db: SQLAlchemy) -> None:
        profile = _make_profile(info_professionnelle={"nom_media": ["A", "B"]})
        assert profile.get_first_value("nom_media") == "A"

    def test_empty_list(self, db: SQLAlchemy) -> None:
        profile = _make_profile(info_professionnelle={"nom_media": []})
        assert profile.get_first_value("nom_media") == ""

    def test_unknown_key(self, db: SQLAlchemy) -> None:
        profile = _make_profile()
        assert profile.get_first_value("does_not_exist") == ""


class TestKYCProfileBwTriggers:
    """``business_wall`` dict is a flag-bag of BW types."""

    def test_get_all_bw_trigger_filters_truthy(self, db: SQLAlchemy) -> None:
        profile = _make_profile(
            business_wall={
                "media": True,
                "pr": False,
                "leaders_experts": True,
            },
        )
        result = profile.get_all_bw_trigger()
        assert set(result) == {"media", "leaders_experts"}

    def test_get_first_bw_trigger_returns_one(self, db: SQLAlchemy) -> None:
        profile = _make_profile(business_wall={"media": True})
        assert profile.get_first_bw_trigger() == "media"

    def test_get_first_bw_trigger_empty(self, db: SQLAlchemy) -> None:
        profile = _make_profile()
        assert profile.get_first_bw_trigger() == ""


class TestKYCProfileSetValueBranches:
    """``set_value`` dispatches per dict location."""

    def test_sets_show_contact_details(self, db: SQLAlchemy) -> None:
        profile = _make_profile(show_contact_details={"k": "old"})
        profile.set_value("k", "new")
        assert profile.show_contact_details["k"] == "new"

    def test_sets_info_personnelle(self, db: SQLAlchemy) -> None:
        profile = _make_profile(info_personnelle={"k": "old"})
        profile.set_value("k", "new")
        assert profile.info_personnelle["k"] == "new"

    def test_sets_info_hobby(self, db: SQLAlchemy) -> None:
        profile = _make_profile(info_hobby={"k": "old"})
        profile.set_value("k", "new")
        assert profile.info_hobby["k"] == "new"

    def test_sets_business_wall(self, db: SQLAlchemy) -> None:
        profile = _make_profile(business_wall={"k": True})
        profile.set_value("k", False)
        assert profile.business_wall["k"] is False

    def test_set_value_unknown_field_is_noop(self, db: SQLAlchemy) -> None:
        """Silently drops unknown keys — preserves the partial-import
        tolerance the ``.get`` accessors rely on."""
        profile = _make_profile()
        profile.set_value("totally_unknown_key", "value")
        # Storage dicts unchanged.
        assert profile.show_contact_details == {}
        assert profile.info_professionnelle == {}


class TestKYCProfileGetValueBranches:
    """``get_value`` walks each storage dict in turn."""

    def test_reads_show_contact_details(self, db: SQLAlchemy) -> None:
        profile = _make_profile(show_contact_details={"mobile_PRESSE": True})
        assert profile.get_value("mobile_PRESSE") is True

    def test_reads_info_hobby(self, db: SQLAlchemy) -> None:
        profile = _make_profile(info_hobby={"hobby_key": "fishing"})
        assert profile.get_value("hobby_key") == "fishing"

    def test_reads_business_wall(self, db: SQLAlchemy) -> None:
        profile = _make_profile(business_wall={"bw_key": True})
        assert profile.get_value("bw_key") is True


class TestKYCProfileContactDetails:
    """``all_contact_details`` rebuilds a checkbox-shaped dict from the
    ``show_contact_details`` JSON, and ``parse_form_contact_details``
    reverses the operation. They're pure dict transforms."""

    def test_all_contact_details_unchecked_by_default(
        self, db: SQLAlchemy
    ) -> None:
        profile = _make_profile()
        data = profile.all_contact_details()
        # Every ContactTypeEnum value must appear as a key.
        for ct in ContactTypeEnum:
            entry = data[ct.name]
            assert entry["label"] == str(ct)
            assert entry["mobile_key"] == f"mobile_{ct.name}"
            assert entry["email_key"] == f"email_{ct.name}"
            assert entry["mobile"] == ""
            assert entry["email"] == ""

    def test_all_contact_details_reflects_checked(
        self, db: SQLAlchemy
    ) -> None:
        first = next(iter(ContactTypeEnum))
        profile = _make_profile(
            show_contact_details={
                f"mobile_{first.name}": True,
                f"email_{first.name}": True,
            },
        )
        data = profile.all_contact_details()
        assert data[first.name]["mobile"] == "checked"
        assert data[first.name]["email"] == "checked"

    def test_parse_form_contact_details_round_trip(
        self, db: SQLAlchemy
    ) -> None:
        first = next(iter(ContactTypeEnum))
        profile = _make_profile()
        form = {f"mobile_{first.name}": "on"}
        profile.parse_form_contact_details(form)
        assert profile.show_contact_details[f"mobile_{first.name}"] is True
        # Unset keys roll over to False.
        assert profile.show_contact_details[f"email_{first.name}"] is False


class TestCloneKycProfile:
    """``clone_kycprofile`` returns a brand-new instance that mirrors
    every non-identity field."""

    def test_clones_all_fields(self, db: SQLAlchemy) -> None:
        orig = _make_profile(
            profile_id="P1",
            profile_code="C1",
            profile_label="Label",
            profile_community="press",
            contact_type="CT",
            display_level=3,
            presentation="hello",
            show_contact_details={"a": True},
            info_personnelle={"b": "c"},
            info_professionnelle={"d": "e"},
            match_making={"f": ["g"]},
            info_hobby={"h": "i"},
            business_wall={"media": True},
        )
        clone = clone_kycprofile(orig)
        assert clone is not orig
        assert clone.profile_id == "P1"
        assert clone.profile_label == "Label"
        assert clone.display_level == 3
        assert clone.show_contact_details == {"a": True}
        assert clone.info_personnelle == {"b": "c"}
        assert clone.match_making == {"f": ["g"]}
        assert clone.business_wall == {"media": True}


class TestCloneUser:
    """``clone_user`` builds a clone with marker fields flipped
    (``is_clone=True``, ``active=False``, fresh ``email`` /
    ``fs_uniquifier``) and copies everything else verbatim."""

    def test_does_not_clone_a_clone(self, db: SQLAlchemy) -> None:
        orig = _make_user(is_clone=True, email="clone@x")
        assert clone_user(orig) is orig

    def test_clones_pure_user(self, db: SQLAlchemy) -> None:
        orig = _make_user(
            email="real@example.com",
            email_secours="backup@example.com",
            first_name="Real",
            last_name="User",
            gender="F",
            tel_mobile="+33000000000",
            login_count=7,
            active=True,
            gcu_acceptation=True,
            karma=42.0,
            status="Confirmed",
        )
        orig.profile = _make_profile(profile_label="X")
        orig.id = 99

        clone = clone_user(orig)

        assert clone is not orig
        assert clone.is_clone is True
        assert clone.active is False  # clone never active.
        assert clone.cloned_user_id == 99
        # Fresh identity:
        assert clone.email.startswith("fake_")
        assert clone.email.endswith("@example.com")
        assert clone.fs_uniquifier != orig.fs_uniquifier
        # Original e-mail preserved sideways:
        assert clone.email_safe_copy == "real@example.com"
        # Verbatim copies:
        assert clone.first_name == "Real"
        assert clone.last_name == "User"
        assert clone.gender == "F"
        assert clone.tel_mobile == "+33000000000"
        assert clone.login_count == 7
        assert clone.karma == 42.0
        assert clone.status == "Confirmed"
        assert clone.gcu_acceptation is True
        # Profile cloned (new instance, same data):
        assert clone.profile is not orig.profile
        assert clone.profile.profile_label == "X"


class TestMergeValuesFromOtherUser:
    """``merge_values_from_other_user`` reverses a clone — the original
    user inherits every field from the modified clone."""

    def test_merge_overwrites_fields(self, db: SQLAlchemy) -> None:
        orig = _make_user(
            email="old@example.com",
            first_name="Old",
            last_name="Name",
            karma=1.0,
            status="Débutant",
            is_clone=False,
        )
        orig.profile = _make_profile(profile_label="old")

        clone = _make_user(
            email_safe_copy="new@example.com",
            email_secours="rescue@example.com",
            first_name="New",
            last_name="Name2",
            karma=99.0,
            status="Expert",
            is_clone=True,
            login_count=12,
            active=True,
        )
        clone.profile = _make_profile(profile_label="new")

        merge_values_from_other_user(orig, clone)

        assert orig.email == "new@example.com"
        assert orig.email_safe_copy == ""
        assert orig.email_secours == "rescue@example.com"
        assert orig.first_name == "New"
        assert orig.last_name == "Name2"
        assert orig.karma == 99.0
        assert orig.status == "Expert"
        assert orig.login_count == 12
        assert orig.is_clone is False
        assert orig.cloned_user_id == 0
        assert orig.active is True
        # Profile re-cloned, so a brand-new instance carrying the
        # modified data:
        assert orig.profile is not clone.profile
        assert orig.profile.profile_label == "new"
