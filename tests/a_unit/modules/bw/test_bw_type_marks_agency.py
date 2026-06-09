# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `bw_type_marks_agency` in
`app.modules.bw.bw_activation.user_utils`.

This helper decides whether a BW row is a press agency, based on
its `type_entreprise_media` label. The decision drives two
downstream behaviours :

- the « représenter mes clients » flow (agencies can publish for
  client orgs)
- the « est-ce une agence » badge on the BW profile page

The check is a literal substring match on « Agence de presse »
(the French ontology label). Pin so a future label rename surfaces
immediately instead of silently turning every agency invisible to
the client-publishing flow.
"""

from __future__ import annotations

from app.modules.bw.bw_activation.user_utils import bw_type_marks_agency


class TestBwTypeMarksAgency:
    def test_exact_label_returns_true(self):
        """Canonical case : the column carries only the agency
        label."""
        assert bw_type_marks_agency("Agence de presse") is True

    def test_substring_of_comma_separated_returns_true(self):
        """The `type_entreprise_media` column is a free-text multi-
        select (no enforced enum). Agencies often carry multiple
        labels — pin the substring match."""
        assert bw_type_marks_agency("Agence de presse, Quotidien régional") is True
        assert bw_type_marks_agency("Quotidien, Agence de presse, Hebdomadaire") is True

    def test_none_returns_false(self):
        """A BW row with an empty `type_entreprise_media` column is
        not flagged as an agency. Pin the defensive False so a
        future regression that crashes with `None in str` is
        caught."""
        assert bw_type_marks_agency(None) is False

    def test_empty_string_returns_false(self):
        assert bw_type_marks_agency("") is False

    def test_no_agency_label_returns_false(self):
        assert bw_type_marks_agency("Quotidien national") is False

    def test_case_sensitive_lowercase_returns_false(self):
        """The check is intentionally case-sensitive (the ontology
        label is the canonical mixed-case form). A future « let's
        be lenient and lowercase first » regression would widen
        the agency definition silently."""
        assert bw_type_marks_agency("agence de presse") is False

    def test_case_sensitive_uppercase_returns_false(self):
        assert bw_type_marks_agency("AGENCE DE PRESSE") is False

    def test_returns_bool_type(self):
        """Pin the return type. The orig had `bool` defaulting then
        a re-assignment ; the extracted helper must always return a
        real bool (not Optional, not str)."""
        assert isinstance(bw_type_marks_agency("Agence de presse"), bool)
        assert isinstance(bw_type_marks_agency("anything"), bool)
        assert isinstance(bw_type_marks_agency(None), bool)
        assert isinstance(bw_type_marks_agency(""), bool)

    def test_partial_match_inside_word_still_returns_true(self):
        """The substring is matched naively : « Sous-Agence de presse »
        also triggers. Pin so a future regex anchor that's stricter
        than the ontology label intends gets caught."""
        assert bw_type_marks_agency("Sous-Agence de presse régionale") is True

    def test_label_at_start_returns_true(self):
        assert bw_type_marks_agency("Agence de presse régionale") is True

    def test_label_at_end_returns_true(self):
        assert bw_type_marks_agency("Sud-Ouest, Agence de presse") is True
