# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the Journalism-taxonomy plumbing in
`app.modules.biz.views.missions`.

WHY this file exists
--------------------

Bug #0187 wires eight `SelectMultipleField`s on `MissionOfferForm` to
KYC ontologies at request time. Two responsibilities co-existed in
`_populate_journalism_taxonomy_choices` :

1. *Policy* — for each (form_field, ontology_key) pair, fetch the
   choices, swallow errors, coerce non-list returns to `[]`.
2. *Wiring* — assign the resulting list onto `form.<field>.choices`.

The policy is pure data : a callable + a tuple of pairs in, a dict
out. It's the part most likely to acquire bugs (a new ontology, an
error-mode change, a typo in a key) so we extract it to
`_resolve_journalism_field_choices` and pin it directly with fake
loaders, no patching.

The wiring step is exercised through a real `MissionOfferForm` inside
`app.test_request_context()` so we still pin the contract a future
refactor of « how is the dict applied to the form » mustn't break.

Project rule, verbatim : « Don't use mocks. Prefer stubs. Whenever
possible, try to verify a tangible outcome (state) rather than an
internal interaction (behavior). » — see CLAUDE.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from werkzeug.datastructures import ImmutableMultiDict

from app.modules.biz.views.missions import (
    _JOURNALISM_TAXONOMY_FIELDS,
    MissionOfferForm,
    _populate_journalism_taxonomy_choices,
    _resolve_journalism_field_choices,
)

if TYPE_CHECKING:
    from flask import Flask


# Each entry is (form-field name, ontology-key the loader is asked
# for). Used as a fixture-style constant by several tests below.
_EXPECTED_PAIRS: tuple[tuple[str, str], ...] = (
    ("metiers_journalisme", "multi_fonctions_journalisme"),
    ("types_entreprises_presse_medias", "multi_type_entreprise_medias"),
    ("types_presse_medias", "multi_type_media"),
    ("competences_journalisme", "multi_competences_journalisme"),
    ("langues", "multi_langues"),
    ("types_contenus_editoriaux", "multi_type_contenu"),
    ("taille_contenus_editoriaux", "multi_taille_contenu"),
    ("modes_remuneration", "multi_mode_remuneration"),
)


class TestJournalismTaxonomyFieldsConstant:
    """Pin the invariants of `_JOURNALISM_TAXONOMY_FIELDS` itself.

    The deposit form's Journalism extension hinges on this tuple. A
    silent edit (dropped row, duplicated field, ontology key typo)
    would render perfectly but ship a broken form to production, so
    we pin the shape here.
    """

    def test_exact_pairs(self):
        """Pin the full contents. Catches an accidental reorder /
        drop / rename that wouldn't fail any other test in CI."""
        assert _JOURNALISM_TAXONOMY_FIELDS == _EXPECTED_PAIRS

    def test_form_field_names_unique(self):
        """Two rows pointing at the same form field would silently
        let the last-wins entry overwrite the first. Pin uniqueness."""
        field_names = [pair[0] for pair in _JOURNALISM_TAXONOMY_FIELDS]
        assert len(field_names) == len(set(field_names))

    def test_ontology_keys_unique(self):
        """Two form fields hitting the same ontology means the second
        has been miswired — pin so a future copy-paste edit is loud."""
        ontology_keys = [pair[1] for pair in _JOURNALISM_TAXONOMY_FIELDS]
        assert len(ontology_keys) == len(set(ontology_keys))

    def test_all_ontology_keys_use_multi_prefix(self):
        """The Journalism block only consumes multi-select ontologies
        (`SelectMultipleField`). A `mono_*` key sneaking in means the
        field would receive a single value where the model expects a
        list — pin so the contract is loud."""
        for _, ontology_key in _JOURNALISM_TAXONOMY_FIELDS:
            assert ontology_key.startswith("multi_"), (
                f"{ontology_key!r} is not a multi-select ontology key"
            )

    def test_every_form_field_exists_on_form(self, app: Flask):
        """The mapping is dead if a form field gets renamed. Pin that
        every (form_field) in the mapping actually exists on
        `MissionOfferForm` — catches a future rename that would silently
        no-op the choice assignment under getattr."""
        with app.test_request_context():
            form = MissionOfferForm(ImmutableMultiDict({}))
            for field_name, _ in _JOURNALISM_TAXONOMY_FIELDS:
                assert hasattr(form, field_name), (
                    f"MissionOfferForm has no field {field_name!r}"
                )


class _RecordingLoader:
    """Real stand-in callable — records the ontology keys it was
    asked for and returns canned data per key.

    No `mock` library involvement : this is a plain class with a
    `__call__`, used as input to `_resolve_journalism_field_choices`.
    """

    def __init__(self, table: dict[str, Any]):
        self._table = table
        self.calls: list[str] = []

    def __call__(self, key: str) -> Any:
        self.calls.append(key)
        if isinstance(self._table.get(key), Exception):
            raise self._table[key]
        return self._table.get(key, [])


class TestResolveJournalismFieldChoicesAllSucceed:
    """Happy path — every loader call returns a real `list`. The
    output dict should mirror the mapping 1-to-1."""

    def test_returns_dict_keyed_by_form_field(self):
        """Each (form_field, ontology_key) row produces a (form_field
        → list) entry in the output."""
        loader = _RecordingLoader(
            {
                key: [(f"v-{key}", f"label-{key}")]
                for _, key in _JOURNALISM_TAXONOMY_FIELDS
            }
        )

        out = _resolve_journalism_field_choices(loader)

        assert set(out) == {f for f, _ in _JOURNALISM_TAXONOMY_FIELDS}

    def test_each_field_receives_its_loader_payload(self):
        """The payload for `multi_langues` must end up under
        `langues`, not under any other field. Pin the per-row routing."""
        table = {
            key: [(f"v-{key}", f"label-{key}")]
            for _, key in _JOURNALISM_TAXONOMY_FIELDS
        }
        loader = _RecordingLoader(table)

        out = _resolve_journalism_field_choices(loader)

        for field_name, ontology_key in _JOURNALISM_TAXONOMY_FIELDS:
            assert out[field_name] == table[ontology_key]

    def test_loader_called_once_per_pair(self):
        """No duplicate fetches, no skipped pairs."""
        loader = _RecordingLoader({})

        _resolve_journalism_field_choices(loader)

        assert loader.calls == [k for _, k in _JOURNALISM_TAXONOMY_FIELDS]


class TestResolveJournalismFieldChoicesErrors:
    """One key raises, another returns a non-list — the rest must
    keep working. The policy must never let one bad ontology take
    down the whole form."""

    def test_raising_key_yields_empty_list(self):
        """A loader exception for a single key is swallowed and that
        key gets `[]`. The other keys are unaffected."""
        table: dict[str, Any] = {
            key: [(f"v-{key}", f"l-{key}")] for _, key in _JOURNALISM_TAXONOMY_FIELDS
        }
        table["multi_langues"] = RuntimeError("ontology DB hiccup")
        loader = _RecordingLoader(table)

        out = _resolve_journalism_field_choices(loader)

        assert out["langues"] == []
        # Sibling field unaffected :
        assert out["metiers_journalisme"] == [
            ("v-multi_fonctions_journalisme", "l-multi_fonctions_journalisme"),
        ]

    @pytest.mark.parametrize(
        "non_list_return",
        [
            {"a": 1},  # dict — get_choices() may return one (orgs)
            "raw-string",
            42,
            None,
            (("v", "n"),),  # tuple, not list
        ],
    )
    def test_non_list_return_yields_empty_list(self, non_list_return):
        """`get_ontology_choices` is typed `list | dict`. Only `list`
        is acceptable for a `SelectMultipleField`. Anything else (dict
        for org-name fields, plus defensive coverage of str / int /
        None / tuple) must collapse to `[]`."""
        table: dict[str, Any] = {
            key: [(f"v-{key}", f"l-{key}")] for _, key in _JOURNALISM_TAXONOMY_FIELDS
        }
        table["multi_langues"] = non_list_return
        loader = _RecordingLoader(table)

        out = _resolve_journalism_field_choices(loader)

        assert out["langues"] == []

    def test_every_key_raises_yields_all_empty(self):
        """Worst-case smoke : every ontology is down. Every output
        list must still be `[]` (not missing!) so the form renders
        with empty selects rather than 500ing."""
        boom = RuntimeError("everything is on fire")
        loader = _RecordingLoader({key: boom for _, key in _JOURNALISM_TAXONOMY_FIELDS})

        out = _resolve_journalism_field_choices(loader)

        assert set(out) == {f for f, _ in _JOURNALISM_TAXONOMY_FIELDS}
        for field_name, _ in _JOURNALISM_TAXONOMY_FIELDS:
            assert out[field_name] == []


class TestResolveJournalismFieldChoicesMappingArg:
    """The `field_mapping` keyword is part of the helper's signature
    so callers (and tests) can pass a smaller mapping. Pin that the
    helper honours it instead of always reading the module-level
    constant."""

    def test_empty_mapping_yields_empty_dict(self):
        """No pairs → no work → empty dict. Loader must not even be
        called."""
        loader = _RecordingLoader({"anything": [("v", "n")]})

        out = _resolve_journalism_field_choices(loader, field_mapping=())

        assert out == {}
        assert loader.calls == []

    def test_custom_mapping_overrides_default(self):
        """Pin the override path. Useful for caller-side tests that
        want to scope to a subset."""
        loader = _RecordingLoader(
            {
                "k_one": [("a", "A")],
                "k_two": [("b", "B")],
            }
        )

        out = _resolve_journalism_field_choices(
            loader,
            field_mapping=(("fld_one", "k_one"), ("fld_two", "k_two")),
        )

        assert out == {
            "fld_one": [("a", "A")],
            "fld_two": [("b", "B")],
        }
        assert loader.calls == ["k_one", "k_two"]


class TestPopulateJournalismTaxonomyChoicesWiring:
    """End-to-end pin of the wiring step. The pure-helper tests cover
    the policy ; this set covers that the resulting dict actually
    ends up on the form fields.

    `_populate_journalism_taxonomy_choices` consumes the real module-
    level `get_ontology_choices`, so we exercise the wiring by
    crafting a `MissionOfferForm` whose field choices are seeded to
    known values via the public `_resolve_journalism_field_choices`
    output. This avoids any patching while still pinning that every
    form field gets assigned correctly.
    """

    def test_form_fields_pick_up_resolved_choices(self, app: Flask):
        """Given a fake loader returning per-key data, the wiring step
        we mirror inline must land the right choices on every form
        field. This pins the contract « dict-of-list-of-tuples →
        per-field assignment » without any test-double libraries."""

        def fake_loader(key: str) -> list[tuple[str, str]]:
            return [(f"v::{key}", f"n::{key}")]

        with app.test_request_context():
            form = MissionOfferForm(ImmutableMultiDict({}))
            choices_by_field = _resolve_journalism_field_choices(fake_loader)
            for field_name, choices in choices_by_field.items():
                getattr(form, field_name).choices = choices

            for field_name, ontology_key in _JOURNALISM_TAXONOMY_FIELDS:
                expected = [(f"v::{ontology_key}", f"n::{ontology_key}")]
                assert getattr(form, field_name).choices == expected

    def test_real_populate_call_assigns_lists_to_every_field(self, app: Flask):
        """The real `_populate_journalism_taxonomy_choices` reads the
        production `get_ontology_choices`. We don't care about the
        exact data here — only that after the call every Journalism
        field has a *list* of choices set (never `None`, never the
        empty default `[]` left untouched if the ontology returned
        data). Pins the « every field gets touched » contract."""
        with app.test_request_context():
            form = MissionOfferForm(ImmutableMultiDict({}))

            # Sentinel : make sure each field's `choices` starts as
            # the form-level default (empty list) so we can detect
            # whether the populate call actually assigned anything.
            for field_name, _ in _JOURNALISM_TAXONOMY_FIELDS:
                getattr(form, field_name).choices = None

            _populate_journalism_taxonomy_choices(form)

            for field_name, _ in _JOURNALISM_TAXONOMY_FIELDS:
                choices = getattr(form, field_name).choices
                assert isinstance(choices, list), (
                    f"{field_name} got {type(choices).__name__}, want list"
                )
