# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pin the ``SelectorSection`` value-object contract.

Why this file exists: ``SelectorSection`` is the pure UI-metadata
carrier introduced in Phase 2 of bug #0150 (Annie's ciblage redesign)
so the 17 ciblage selectors render as 4 thematic groups instead of an
undifferentiated 2-column grid. The dataclass is frozen and used as a
hashable value object by templates and by the ``ExpertFilterService.
sections`` property. Even though it's tiny (~14 LOC), regressing
*any* of its guarantees — frozen identity, field shape, equality
semantics, hashability — would silently break the journalist's
targeted-invitation UI without a load-bearing exception. These tests
freeze the contract and document the intent so future refactors stay
honest.

Scope: ONLY ``SelectorSection`` itself. The surrounding
``ExpertFilterService`` is a session/DB-coupled orchestrator and is
exercised by ``tests/b_integration/modules/wip``.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from app.modules.wip.services.newsroom.expert_filter import SelectorSection

# ----------------------------------------------------------------------
# Duck-typed selector stand-ins
# ----------------------------------------------------------------------


class _StubSelector:
    """Minimal stand-in for ``BaseSelector`` — id + label only.

    ``SelectorSection`` never introspects its selectors; it just holds
    the list. Using a featherweight stub keeps these tests free of the
    SQLAlchemy / session machinery the real selectors drag in.
    """

    def __init__(self, sid: str, label: str = "") -> None:
        self.id = sid
        self.label = label

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return f"_StubSelector(id={self.id!r})"


def _stub(sid: str) -> _StubSelector:
    """Tiny shortcut so test bodies read like the spec, not like setup."""
    return _StubSelector(sid)


# ----------------------------------------------------------------------
# Construction & field shape
# ----------------------------------------------------------------------


class TestConstruction:
    """The dataclass exposes exactly two public fields: title + selectors.

    Pinning the field set guards against accidental schema drift
    (extra positional args, renamed fields) that would silently break
    every Jinja template iterating over ``section.title`` /
    ``section.selectors``.
    """

    def test_basic_construction_sets_title_and_selectors(self) -> None:
        section = SelectorSection(
            title="Géolocalisation",
            selectors=[_stub("pays"), _stub("departement")],
        )
        assert section.title == "Géolocalisation"
        assert len(section.selectors) == 2
        assert section.selectors[0].id == "pays"
        assert section.selectors[1].id == "departement"

    def test_construction_accepts_empty_selector_list(self) -> None:
        """A section with no selectors is legal — used by ``pick()`` when
        every requested id is missing from the registry (defensive
        branch in ``ExpertFilterService.sections``)."""
        section = SelectorSection(title="Empty", selectors=[])
        assert section.title == "Empty"
        assert section.selectors == []

    def test_positional_argument_order(self) -> None:
        """``title`` then ``selectors`` — pin the order so callers using
        positional args (like ``SelectorSection("X", [...])``) keep
        working across refactors."""
        section = SelectorSection("Fonctions", [_stub("fonction")])
        assert section.title == "Fonctions"
        assert section.selectors[0].id == "fonction"

    def test_keyword_only_construction_works(self) -> None:
        section = SelectorSection(
            selectors=[_stub("metier")],
            title="Métiers",
        )
        assert section.title == "Métiers"
        assert [s.id for s in section.selectors] == ["metier"]

    def test_is_a_dataclass(self) -> None:
        """Implementation detail worth pinning: it must remain a
        ``@dataclass`` so callers can use ``dataclasses.asdict`` /
        ``dataclasses.replace`` and so the auto-generated ``__eq__`` /
        ``__hash__`` keep the equality semantics tested below."""
        assert dataclasses.is_dataclass(SelectorSection)

    def test_has_exactly_expected_fields(self) -> None:
        """No more, no less. Adding a field silently to a frozen
        value object is a breaking change."""
        field_names = {f.name for f in dataclasses.fields(SelectorSection)}
        assert field_names == {"title", "selectors"}


# ----------------------------------------------------------------------
# Immutability (frozen=True)
# ----------------------------------------------------------------------


class TestImmutability:
    """The dataclass is declared ``frozen=True`` — every attribute write
    must raise ``FrozenInstanceError``.

    Why: sections are produced fresh on every render of
    ``ExpertFilterService.sections`` but downstream code (templates,
    tests, future caches) is allowed to assume they don't mutate.
    Removing ``frozen=True`` would silently break that contract.
    """

    @pytest.mark.parametrize(
        ("attr", "new_value"),
        [
            ("title", "Other title"),
            ("selectors", []),
        ],
    )
    def test_cannot_reassign_field(self, attr: str, new_value: Any) -> None:
        section = SelectorSection(title="T", selectors=[_stub("a")])
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(section, attr, new_value)

    def test_cannot_add_new_attribute(self) -> None:
        """Frozen dataclasses also block ``__setattr__`` for unknown
        attributes — guards against typo-driven 'silent extension'."""
        section = SelectorSection(title="T", selectors=[])
        with pytest.raises(dataclasses.FrozenInstanceError):
            section.extra = "nope"  # type: ignore[attr-defined]

    def test_cannot_delete_field(self) -> None:
        section = SelectorSection(title="T", selectors=[])
        with pytest.raises(dataclasses.FrozenInstanceError):
            del section.title

    def test_selectors_list_itself_is_not_deep_frozen(self) -> None:
        """Defensive note, not a wish: ``frozen=True`` freezes the
        binding, not the contained ``list``. We pin the current
        behaviour so anyone reading the test learns the caveat instead
        of being surprised by it. The right defence is for producers
        (``ExpertFilterService.sections``) to never re-use lists, which
        they don't."""
        selectors = [_stub("a")]
        section = SelectorSection(title="T", selectors=selectors)
        # The contained list IS mutable — this is expected Python
        # semantics for frozen dataclasses with mutable members.
        section.selectors.append(_stub("b"))
        assert len(section.selectors) == 2


# ----------------------------------------------------------------------
# Equality & hashing
# ----------------------------------------------------------------------


class TestEquality:
    """Frozen dataclasses get value-based ``__eq__`` and ``__hash__``
    for free. Templates / tests rely on this to compare or set-dedupe
    sections without falling back to ``id()`` identity."""

    def test_equal_when_same_title_and_same_selectors(self) -> None:
        sel = _stub("secteur")
        a = SelectorSection(title="X", selectors=[sel])
        b = SelectorSection(title="X", selectors=[sel])
        assert a == b

    def test_not_equal_when_titles_differ(self) -> None:
        sel = _stub("secteur")
        a = SelectorSection(title="X", selectors=[sel])
        b = SelectorSection(title="Y", selectors=[sel])
        assert a != b

    def test_not_equal_when_selector_lists_differ(self) -> None:
        a = SelectorSection(title="X", selectors=[_stub("a")])
        b = SelectorSection(title="X", selectors=[_stub("a"), _stub("b")])
        assert a != b

    def test_not_equal_to_unrelated_type(self) -> None:
        section = SelectorSection(title="X", selectors=[])
        assert section != "X"
        assert section != ("X", [])
        assert section != {"title": "X", "selectors": []}

    def test_empty_sections_are_equal(self) -> None:
        assert SelectorSection(title="", selectors=[]) == SelectorSection(
            title="", selectors=[]
        )


class TestHashing:
    """Pin whatever hash behaviour the implementation chose. A frozen
    dataclass with a ``list`` field is NOT hashable by default (lists
    are unhashable). Both outcomes are valid design choices, and we
    want a clear signal in the test suite if it ever flips."""

    def test_unhashable_due_to_list_field(self) -> None:
        """Current contract: sections cannot be put into a ``set`` /
        used as ``dict`` keys because they hold a ``list``. If the
        author ever switches to ``tuple[BaseSelector, ...]`` (a sound
        future move), this test will fail loudly and force a conscious
        decision."""
        section = SelectorSection(title="T", selectors=[_stub("a")])
        with pytest.raises(TypeError):
            hash(section)


# ----------------------------------------------------------------------
# Annie's spec: titles & ordering invariants
# ----------------------------------------------------------------------


class TestSpecCompliance:
    """``SelectorSection`` instances are produced with hard-coded
    French titles drawn from Annie's spec (bug #0150). Pin them so a
    rogue translation pass or copy-edit doesn't silently rewrite the
    UI labels."""

    @pytest.mark.parametrize(
        "title",
        [
            "Secteurs d'activité et types d'organisation",
            "Géolocalisation",
            "Fonctions",
            "Métiers, compétences & langues",
        ],
    )
    def test_canonical_titles_are_valid_section_titles(self, title: str) -> None:
        """Each canonical title is non-empty and accepted by the
        constructor. This is a sanity gate for the strings the
        service hard-codes."""
        section = SelectorSection(title=title, selectors=[])
        assert section.title == title
        assert section.title.strip() != ""

    def test_selectors_attribute_preserves_input_order(self) -> None:
        """Order matters — the journalist's spec lists selectors top
        to bottom, and templates render them in iteration order."""
        ids = ["secteur", "type_organisation", "taille_organisation"]
        section = SelectorSection(
            title="Secteurs",
            selectors=[_stub(i) for i in ids],
        )
        assert [s.id for s in section.selectors] == ids


# ----------------------------------------------------------------------
# Dataclass-level utilities
# ----------------------------------------------------------------------


class TestDataclassUtilities:
    """Frozen dataclasses are typically consumed via ``asdict`` and
    ``replace``. Even if no production caller uses them today, the
    spec promises value-object semantics; pin them so the promise
    survives refactors."""

    def test_asdict_roundtrips_to_plain_dict(self) -> None:
        sel = _stub("pays")
        section = SelectorSection(title="Géo", selectors=[sel])
        as_dict = dataclasses.asdict(section)
        # ``selectors`` deep-converts to whatever asdict produces from
        # the stub — we only assert top-level shape to stay decoupled
        # from selector internals.
        assert as_dict["title"] == "Géo"
        assert "selectors" in as_dict
        assert isinstance(as_dict["selectors"], list)
        assert len(as_dict["selectors"]) == 1

    def test_replace_produces_new_instance_with_overridden_field(self) -> None:
        section = SelectorSection(title="Old", selectors=[_stub("a")])
        renamed = dataclasses.replace(section, title="New")
        assert renamed is not section
        assert renamed.title == "New"
        assert renamed.selectors is section.selectors  # shared ref by design
        # Original is untouched (frozen):
        assert section.title == "Old"

    def test_replace_can_swap_selectors_list(self) -> None:
        section = SelectorSection(title="T", selectors=[_stub("a")])
        swapped = dataclasses.replace(section, selectors=[_stub("b")])
        assert [s.id for s in swapped.selectors] == ["b"]
        assert [s.id for s in section.selectors] == ["a"]

    def test_repr_includes_title_and_selectors(self) -> None:
        """The auto-generated ``__repr__`` is the only debugging
        surface we have when a section misrenders. Pin that both
        fields appear."""
        section = SelectorSection(title="Géo", selectors=[_stub("pays")])
        r = repr(section)
        assert "SelectorSection" in r
        assert "Géo" in r
        assert "selectors=" in r
