# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for the ``search.constants`` module.

This module is thin glue: it exposes a ``COLLECTIONS`` list used by the
sidebar to render the search filter tabs, derived from
``registry.REGISTRY``. The bulk of the per-type metadata lives in
``registry.py``; here we pin two things only:

1. The shape of the helper ``_collection_from`` (private but worth
   testing because it encodes a quirky single-vs-list ``type`` rule
   that ``views.py`` silently depends on).
2. The leading ``"all"`` aggregator entry plus the order/identity of
   the rest of ``COLLECTIONS``, because that order maps 1-to-1 to the
   visible sidebar tabs.

We deliberately do NOT assert on all label/icon strings — those are
defined in ``registry.py`` and already covered by inspection there;
duplicating them here would just create a maintenance burden every
time a copywriter renames a tab.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.modules.search.constants import COLLECTIONS, _collection_from
from app.modules.search.registry import REGISTRY


@dataclass(frozen=True)
class _FakeEntry:
    """Duck-typed stand-in for ``IndexableType``.

    ``_collection_from`` only reads four attributes; using a tiny
    dataclass keeps the test independent from the real registry shape
    and avoids importing SQLAlchemy models just to exercise a mapping
    helper.
    """

    ui_name: str
    label: str
    icon: str
    doc_types: tuple[str, ...]


class TestCollectionFromHappyPath:
    """Pin the structural contract returned by ``_collection_from``."""

    def test_single_doc_type_is_unwrapped_to_a_string(self) -> None:
        # WHY: the view layer treats a string-valued ``type`` as a
        # single exact-match filter. If we accidentally always
        # returned a list, the sidebar would issue OR queries with one
        # element, which works but slows the engine and obscures
        # intent. The "unwrap" branch is load-bearing.
        entry = _FakeEntry(
            ui_name="articles",
            label="Articles",
            icon="newspaper",
            doc_types=("article",),
        )

        result = _collection_from(entry)

        assert result == {
            "name": "articles",
            "label": "Articles",
            "icon": "newspaper",
            "type": "article",
        }
        assert isinstance(result["type"], str)

    def test_multiple_doc_types_become_a_list(self) -> None:
        # WHY: polymorphic buckets (e.g. marketplace = 4 subtypes
        # sharing one sidebar tab) rely on the engine receiving a list
        # so it can OR the discriminators. Losing this branch would
        # silently hide 3 of 4 marketplace subtypes from search.
        entry = _FakeEntry(
            ui_name="marketplace",
            label="Marketplace",
            icon="shopping-bag",
            doc_types=("mission_offer", "project_offer", "job_offer"),
        )

        result = _collection_from(entry)

        assert result == {
            "name": "marketplace",
            "label": "Marketplace",
            "icon": "shopping-bag",
            "type": ["mission_offer", "project_offer", "job_offer"],
        }
        assert isinstance(result["type"], list)

    def test_doc_types_list_is_a_fresh_copy_not_an_alias(self) -> None:
        # WHY: ``_collection_from`` wraps ``doc_types`` with ``list(...)``
        # rather than returning the underlying tuple cast. That copy
        # protects callers who mutate the returned dict from corrupting
        # the registry. Pin the copy semantics so a refactor to
        # ``entry.doc_types`` doesn't quietly leak the registry's
        # immutable tuple as a mutable view.
        doc_types = ("a", "b")
        entry = _FakeEntry("x", "X", "icon", doc_types)

        result = _collection_from(entry)

        assert result["type"] == ["a", "b"]
        assert result["type"] is not doc_types


class TestCollectionFromKeysAndOrdering:
    """Pin the dict key set; downstream Jinja templates depend on it."""

    def test_returned_dict_has_exactly_these_keys(self) -> None:
        # WHY: ``views.py`` and the sidebar template index by
        # ``name`` / ``label`` / ``icon`` / ``type`` directly. Any
        # rename or addition is a breaking change and should be a
        # conscious decision, not a drive-by.
        entry = _FakeEntry("u", "L", "i", ("t",))

        result = _collection_from(entry)

        assert set(result.keys()) == {"name", "label", "icon", "type"}


class TestCollectionsModuleConstant:
    """Pin the public ``COLLECTIONS`` list."""

    def test_first_entry_is_the_all_aggregator(self) -> None:
        # WHY: the "Tout" tab is hard-coded at the top because there is
        # no registry entry that means "everything" — the engine
        # interprets ``type=None`` as "no discriminator filter". If
        # this entry moves or its ``type`` becomes non-None, the
        # default search view stops returning cross-type results.
        assert COLLECTIONS[0] == {
            "name": "all",
            "label": "Tout",
            "icon": "rectangle-stack",
            "type": None,
        }

    def test_collections_length_matches_registry_plus_all(self) -> None:
        # WHY: this guards against accidental duplication or omission
        # when someone adds a new ``IndexableType`` to the registry.
        # The constant must stay in sync 1:1 with the registry plus
        # the single hand-written "all" prefix.
        assert len(COLLECTIONS) == len(REGISTRY) + 1

    def test_collection_names_are_unique(self) -> None:
        # WHY: ``name`` is used as the URL filter token and the sidebar
        # tab key. Duplicates would silently make one of the tabs
        # unreachable and confuse the active-tab highlight logic.
        names = [entry["name"] for entry in COLLECTIONS]
        assert len(names) == len(set(names))

    def test_collections_after_all_are_derived_from_registry_in_order(
        self,
    ) -> None:
        # WHY: the sidebar renders ``COLLECTIONS`` top-to-bottom. The
        # contract is "all" first, then registry order. A future
        # refactor that reorders the comprehension (e.g. sorting
        # alphabetically) would silently shuffle the UI; pin the
        # registry-order invariant explicitly.
        derived = COLLECTIONS[1:]
        expected = [_collection_from(entry) for entry in REGISTRY]
        assert derived == expected


@pytest.mark.parametrize(
    ("ui_name", "expected_type"),
    [
        ("articles", "article"),
        ("press-releases", "press_release"),
        ("events", "event"),
        ("members", "user"),
        ("orgs", "organisation"),
    ],
)
class TestSingleTypeCollections:
    """Pin the single-discriminator buckets from the real registry."""

    def test_single_type_collection_has_string_type(
        self, ui_name: str, expected_type: str
    ) -> None:
        # WHY: these five UI tabs all map to exactly one document
        # discriminator. Parametrizing keeps the assertions tight and
        # makes a future "groups" re-introduction (currently removed,
        # see the registry comment) a one-line diff.
        match = next(c for c in COLLECTIONS if c["name"] == ui_name)
        assert match["type"] == expected_type
        assert isinstance(match["type"], str)


class TestMarketplaceCollection:
    """The marketplace bucket is the only multi-type entry."""

    def test_marketplace_type_is_a_list_of_all_four_subtypes(self) -> None:
        # WHY: marketplace is the lone polymorphic bucket and the only
        # place where the list-branch of ``_collection_from`` actually
        # fires in production. If someone accidentally collapses it to
        # a single string (e.g. while normalising the registry), three
        # of the four marketplace subtypes silently disappear from the
        # search results.
        match = next(c for c in COLLECTIONS if c["name"] == "marketplace")
        assert isinstance(match["type"], list)
        assert set(match["type"]) == {
            "mission_offer",
            "project_offer",
            "job_offer",
            "editorial_product",
        }
