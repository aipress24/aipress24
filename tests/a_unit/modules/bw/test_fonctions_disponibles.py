# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `_fonctions_disponibles_for_bw` in
`app.modules.bw.bw_activation.user_utils`.

This helper feeds the BW activation step-2 « Fonction/Titre »
autocomplete with every KYC fonction relevant for the BW type being
activated.

The dispatch is driven by `BW_TYPE_FONCTION_SOURCES` (in
`app.models.auth`). For each BW type, the dict lists which profile
attributes to pull fonctions from (e.g. `media` → only
`fonctions_journalisme` ; `pr` → 3 sources combined).

Bug #0107 (pinned here) : the previous implementation defaulted to
the FIRST item of an unordered KYC list — often a misleading value
(e.g. « chef de projet média » for a « rédacteur en chef »). The fix
expose ALL relevant fonctions so the template can offer autocomplete.
"""

from __future__ import annotations

from app.models.auth import BW_TYPE_FONCTION_SOURCES
from app.modules.bw.bw_activation.user_utils import (
    _fonctions_disponibles_for_bw,
)


class _Profile:
    """Minimal profile stand-in : only carries the attributes the
    SUT reads via getattr."""

    def __init__(self, **fonctions_attrs) -> None:
        # Profile attributes default to empty list (the KYC layer's
        # behaviour for unfilled multi-selects).
        for attr in (
            "fonctions_journalisme",
            "fonctions_org_priv_detail",
            "fonctions_pol_adm_detail",
            "fonctions_ass_syn_detail",
            "toutes_fonctions",
        ):
            setattr(self, attr, fonctions_attrs.get(attr, []))


class _User:
    """Minimal user stand-in : only exposes `profile`."""

    def __init__(self, profile: object | None) -> None:
        self.profile = profile


def _user_with_profile(**fonctions_attrs) -> _User:
    """Build a User stand-in with a profile that exposes the
    requested fonctions_* attributes. Other attrs default to empty list.

    The helper only reads `user.profile` ; everything else is
    irrelevant."""
    return _User(_Profile(**fonctions_attrs))


class TestNoProfile:
    def test_no_profile_returns_empty_list(self):
        """A user without a KYC profile (just signed up, freshly-
        created) is not crashed by this helper. Empty list = the
        autocomplete dropdown stays empty until the user fills KYC."""
        user = _User(profile=None)
        assert _fonctions_disponibles_for_bw(user, "media") == []

    def test_no_profile_attribute_returns_empty_list(self):
        """`getattr(user, "profile", None)` — defensive against
        legacy User rows that lack the `profile` attribute entirely."""

        class _BareUser:
            pass

        assert _fonctions_disponibles_for_bw(_BareUser(), "media") == []


class TestBwTypeDispatch:
    def test_media_uses_fonctions_journalisme_only(self):
        """`media` BW type → only the journalism fonctions."""
        user = _user_with_profile(
            fonctions_journalisme=["Rédacteur en chef", "Reporter"],
            fonctions_org_priv_detail=["Should not appear"],
        )
        result = _fonctions_disponibles_for_bw(user, "media")
        assert "Rédacteur en chef" in result
        assert "Reporter" in result
        assert "Should not appear" not in result

    def test_pr_combines_three_sources(self):
        """`pr` → org_priv + pol_adm + ass_syn. Pin so a future
        rename of any of those source attrs is caught by
        the no-results assertion."""
        user = _user_with_profile(
            fonctions_org_priv_detail=["Directeur com"],
            fonctions_pol_adm_detail=["Conseiller"],
            fonctions_ass_syn_detail=["Délégué"],
            fonctions_journalisme=["Should not appear"],
        )
        result = _fonctions_disponibles_for_bw(user, "pr")
        assert "Directeur com" in result
        assert "Conseiller" in result
        assert "Délégué" in result
        assert "Should not appear" not in result

    def test_unknown_bw_type_falls_back_to_toutes_fonctions(self):
        """A bw_type we don't recognise (« bogus » or a future new
        type not yet added) falls back to `toutes_fonctions` — the
        union of every fonction the user has. Pin so the activation
        flow still shows SOMETHING in the dropdown."""
        user = _user_with_profile(
            toutes_fonctions=["Anything", "Else"],
            fonctions_journalisme=["Specific"],
        )
        result = _fonctions_disponibles_for_bw(user, "bogus-bw-type")
        assert result == ["Anything", "Else"]

    def test_none_bw_type_falls_back_to_toutes_fonctions(self):
        """No bw_type yet selected → fall through to the catch-all."""
        user = _user_with_profile(
            toutes_fonctions=["A", "B"],
        )
        result = _fonctions_disponibles_for_bw(user, None)
        assert result == ["A", "B"]


class TestDeduplication:
    def test_duplicate_across_sources_deduplicated(self):
        """A value appearing in two source attributes is returned
        ONCE (set-tracked dedup). Pin so the autocomplete dropdown
        doesn't show « Directeur » twice when the user happens to
        carry the same value in two ontology sub-attributes."""
        user = _user_with_profile(
            fonctions_org_priv_detail=["Directeur", "Manager"],
            fonctions_pol_adm_detail=["Directeur"],  # duplicate
            fonctions_ass_syn_detail=[],
        )
        result = _fonctions_disponibles_for_bw(user, "pr")
        assert result.count("Directeur") == 1
        assert "Manager" in result

    def test_preserves_order_of_first_occurrence(self):
        """Pin the order : within a source, attribute order is
        preserved ; across sources, first-occurrence-wins. Catches
        a future « let's sort alphabetically » regression that would
        break the « most-likely-first » ranking the KYC ontology
        gives us."""
        user = _user_with_profile(
            fonctions_org_priv_detail=["A", "B"],
            fonctions_pol_adm_detail=["C"],
            fonctions_ass_syn_detail=["B", "D"],  # B already seen, D new
        )
        result = _fonctions_disponibles_for_bw(user, "pr")
        assert result == ["A", "B", "C", "D"]


class TestEmptyValuesFiltered:
    def test_empty_strings_skipped(self):
        """Empty-string values (KYC import edge case) are silently
        dropped — the autocomplete must not surface blank options."""
        user = _user_with_profile(
            fonctions_journalisme=["Reporter", "", "Editor"],
        )
        result = _fonctions_disponibles_for_bw(user, "media")
        assert "" not in result
        assert "Reporter" in result
        assert "Editor" in result

    def test_none_values_skipped(self):
        """None values in the source attr (data import quirk) get
        silently dropped — the truthy check (`if value`) handles
        them. Pin so a refactor that uses `is not None` doesn't
        accidentally let Nones through."""
        user = _user_with_profile(
            fonctions_journalisme=[None, "Reporter"],
        )
        result = _fonctions_disponibles_for_bw(user, "media")
        assert None not in result
        assert "Reporter" in result


class TestSourceAttrMissing:
    def test_missing_source_attr_skipped(self):
        """If a profile attr listed in BW_TYPE_FONCTION_SOURCES
        doesn't exist on the profile (legacy profile, attr renamed),
        the helper skips it via `getattr(profile, attr, None) or []`.
        Pin so a future ontology refactor doesn't crash the
        activation flow."""

        class _PartialProfile:
            # Missing all fonctions_* attrs.
            pass

        user = _User(profile=_PartialProfile())
        result = _fonctions_disponibles_for_bw(user, "pr")
        # No source attr to read → empty list.
        assert result == []

    def test_none_source_attr_treated_as_empty(self):
        """An attr that's explicitly None (KYC import set null)
        is treated as empty without crashing."""

        class _NoneJournalismeProfile:
            fonctions_journalisme = None

        user = _User(profile=_NoneJournalismeProfile())
        result = _fonctions_disponibles_for_bw(user, "media")
        assert result == []


class TestBwTypeFonctionSourcesInvariants:
    """Pin structural invariants on the source-mapping dict. A
    refactor that empties a tuple or adds a None-valued mapping
    would silently break the autocomplete for that BW type."""

    def test_all_keys_are_strings(self):
        for k in BW_TYPE_FONCTION_SOURCES:
            assert isinstance(k, str)

    def test_all_values_are_tuples_of_strings(self):
        for k, v in BW_TYPE_FONCTION_SOURCES.items():
            assert isinstance(v, tuple), (
                f"BW_TYPE_FONCTION_SOURCES[{k!r}] must be a tuple"
            )
            for attr in v:
                assert isinstance(attr, str)
                assert attr.startswith("fonctions_"), (
                    f"Source attr {attr!r} (for BW type {k!r}) doesn't "
                    "follow the `fonctions_*` naming convention."
                )

    def test_no_empty_source_tuples(self):
        """A BW type mapped to an empty tuple would silently produce
        no autocomplete options. Pin so a refactor accident gets
        caught at PR time."""
        for k, v in BW_TYPE_FONCTION_SOURCES.items():
            assert len(v) > 0, f"BW_TYPE_FONCTION_SOURCES[{k!r}] is empty"

    def test_media_present(self):
        """`media` is the most-used BW type — pin its presence."""
        assert "media" in BW_TYPE_FONCTION_SOURCES
