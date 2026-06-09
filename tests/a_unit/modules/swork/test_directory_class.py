# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `Directory` in `app.modules.swork.common.directory`.

`Directory` is a small pure-logic helper used by every "list of people /
orgs / groups" page in the swork module. It takes a flat list of
objects and produces an alphabet-indexed dictionary so templates can
render an A-Z directory like a phone book.

The class also supports two features the templates rely on:

  * a custom `key` attribute (default ``"name"``), used both for the
    bucket letter and the in-bucket sort order;
  * an optional `vm_class` view-model wrapper applied to each object
    on the way into the bucket — pages use this to attach
    presentation methods without polluting the domain model.

Because the class is tiny (~50 LOC) but appears in three list
components, regressions here would silently break navigation. The
tests below pin the contract: bucketing, ordering, empty input,
empty/missing key values, wrapping, indexing, and `keys()`
delegation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

import pytest

from app.modules.swork.common import Directory
from app.modules.swork.common.directory import Directory as DirectoryClass


@dataclass
class Item:
    """Minimal stand-in for any "named" domain object."""

    name: str


@dataclass
class Contact:
    """Stand-in with a non-default key attribute."""

    surname: str
    name: str = ""


# A namedtuple is a common stand-in for read-only rows; the directory
# does duck-typed attribute access, so this must keep working.
class Person(NamedTuple):
    name: str


class ViewModel:
    """Stand-in view-model wrapper used to verify `vm_class` wrapping."""

    def __init__(self, obj):
        self.wrapped = obj

    @property
    def name(self):
        return self.wrapped.name


class TestEmptyInput:
    """An empty source list must produce an empty directory.

    Templates iterate `directory.keys()` to render the A-Z index, so
    an empty input must not raise and must yield no letters.
    """

    def test_empty_list_yields_no_keys(self):
        directory = Directory([])
        assert list(directory.keys()) == []

    def test_empty_list_preserves_objects_attribute(self):
        directory = Directory([])
        assert directory.objects == []

    def test_empty_directory_getitem_returns_empty_list(self):
        # `directory` is a defaultdict, so missing keys must not raise
        # — this is what allows templates to ask for any letter blindly.
        directory = Directory([])
        assert directory["Z"] == []


class TestSingleLetterGrouping:
    """When all objects share the same first letter, one bucket holds them all."""

    def test_all_objects_share_bucket(self):
        items = [Item("toto"), Item("titi"), Item("tata")]
        directory = Directory(items)

        assert list(directory.keys()) == ["T"]
        assert len(directory["T"]) == 3

    def test_in_bucket_sort_is_alphabetical(self):
        # In-bucket order matters: templates render the bucket as-is.
        items = [Item("toto"), Item("titi"), Item("tata")]
        directory = Directory(items)

        names = [obj.name for obj in directory["T"]]
        assert names == ["tata", "titi", "toto"]

    def test_lowercase_and_uppercase_share_bucket(self):
        # `get_key` uppercases the first character, so mixed-case
        # entries must land in the same bucket.
        items = [Item("Alice"), Item("alfred")]
        directory = Directory(items)

        assert list(directory.keys()) == ["A"]
        assert len(directory["A"]) == 2


class TestMultiLetterGrouping:
    """Objects with distinct first letters must land in distinct buckets.

    The directory uses a defaultdict, but the *iteration* order of
    keys matters for the A-Z navigation rail: it follows the sorted
    input list, which the constructor sorts alphabetically.
    """

    def test_distinct_first_letters_create_distinct_buckets(self):
        items = [Item("alpha"), Item("bravo"), Item("charlie")]
        directory = Directory(items)

        assert set(directory.keys()) == {"A", "B", "C"}
        assert [o.name for o in directory["A"]] == ["alpha"]
        assert [o.name for o in directory["B"]] == ["bravo"]
        assert [o.name for o in directory["C"]] == ["charlie"]

    def test_key_iteration_is_alphabetical(self):
        # Because the input is sorted before bucketing and dict
        # iteration preserves insertion order in Python 3.7+, the
        # keys must come out alphabetically — even when input is
        # shuffled.
        items = [
            Item("charlie"),
            Item("alpha"),
            Item("bravo"),
            Item("apricot"),
        ]
        directory = Directory(items)

        assert list(directory.keys()) == ["A", "B", "C"]

    def test_bucket_contents_independent(self):
        items = [Item("ada"), Item("bob"), Item("alan")]
        directory = Directory(items)

        assert [o.name for o in directory["A"]] == ["ada", "alan"]
        assert [o.name for o in directory["B"]] == ["bob"]


class TestFallbackBucket:
    """Empty / falsy attribute values must land in the "?" bucket.

    Real data sometimes has missing `name` fields; the fallback keeps
    the directory from crashing and gives the template a "no name"
    bucket it can choose to hide or render specially.
    """

    def test_empty_string_falls_to_question_mark(self):
        items = [Item(""), Item("alice")]
        directory = Directory(items)

        assert "?" in directory.keys()  # noqa: SIM118 — pin keys() contract
        assert directory["?"][0].name == ""

    def test_multiple_empty_strings_grouped_in_question_mark(self):
        items = [Item(""), Item(""), Item("bob")]
        directory = Directory(items)

        assert len(directory["?"]) == 2
        assert [o.name for o in directory["B"]] == ["bob"]

    def test_only_empty_strings_yields_only_question_mark_bucket(self):
        directory = Directory([Item(""), Item("")])

        assert list(directory.keys()) == ["?"]
        assert len(directory["?"]) == 2


class TestVmClassWrapping:
    """`vm_class`, if set on the subclass, wraps every bucketed object.

    This is the hook pages use to attach presentation logic (URLs,
    labels…) without polluting the domain model. When unset, the raw
    object must be stored as-is.
    """

    def test_default_no_vm_class_returns_bare_object(self):
        items = [Item("alice")]
        directory = Directory(items)

        # Bare object must be the exact same instance.
        assert directory["A"][0] is items[0]

    def test_vm_class_wraps_each_object(self):
        class WrappingDirectory(Directory):
            vm_class = ViewModel

        items = [Item("alice"), Item("bob")]
        directory = WrappingDirectory(items)

        assert all(isinstance(o, ViewModel) for o in directory["A"])
        assert all(isinstance(o, ViewModel) for o in directory["B"])
        assert directory["A"][0].wrapped is items[0]

    def test_wrap_method_called_directly(self):
        # `wrap` is part of the (informal) public surface; subclasses
        # override it. Make sure the default behaviour is documented.
        directory = Directory([])
        sentinel = Item("x")
        assert directory.wrap(sentinel) is sentinel


class TestCustomKey:
    """A custom `key` parameter overrides the default ``"name"`` attribute.

    Components that list objects without a `name` attribute (e.g.
    contacts indexed by `surname`) rely on this.
    """

    def test_custom_key_buckets_by_other_attribute(self):
        items = [
            Contact(surname="Zorro"),
            Contact(surname="Alpha"),
            Contact(surname="Beta"),
        ]
        directory = Directory(items, key="surname")

        assert list(directory.keys()) == ["A", "B", "Z"]

    def test_custom_key_used_for_sort(self):
        items = [
            Contact(surname="Zoe"),
            Contact(surname="Anne"),
            Contact(surname="Adam"),
        ]
        directory = Directory(items, key="surname")

        # In-bucket sort must use the same custom key.
        assert [c.surname for c in directory["A"]] == ["Adam", "Anne"]

    def test_default_key_is_name(self):
        # Pin the default. Changing it would break every existing
        # caller silently.
        items = [Item("xavier")]
        directory = Directory(items)
        assert directory.key == "name"


class TestGetItemAndKeys:
    """`__getitem__` and `keys()` delegate to the inner defaultdict.

    Templates rely on both: `keys()` to render the A-Z rail and
    `directory[letter]` to render each section.
    """

    def test_getitem_returns_bucket_list(self):
        items = [Item("alice"), Item("bob")]
        directory = Directory(items)

        bucket = directory["A"]
        assert isinstance(bucket, list)
        assert bucket[0].name == "alice"

    def test_getitem_missing_key_returns_empty_list(self):
        # Defaultdict semantics — verify the contract holds at the
        # `__getitem__` level so templates can ask blindly.
        directory = Directory([Item("alice")])
        assert directory["Z"] == []

    def test_keys_view_reflects_inserted_buckets(self):
        directory = Directory([Item("alice"), Item("bob")])

        keys = directory.keys()
        assert "A" in keys
        assert "B" in keys
        assert "C" not in keys


class TestIterationWithDifferentObjectShapes:
    """Directory works on duck-typed objects: dataclasses and namedtuples.

    Templates pass whatever the repository yields — anything with the
    chosen attribute must be supported.
    """

    @pytest.mark.parametrize(
        "make_obj",
        [Item, Person],
        ids=["dataclass", "namedtuple"],
    )
    def test_supports_various_object_types(self, make_obj):
        objs = [make_obj("charlie"), make_obj("alice"), make_obj("bob")]
        directory = Directory(objs)

        assert set(directory.keys()) == {"A", "B", "C"}
        assert directory["A"][0].name == "alice"


class TestPublicReexport:
    """The `Directory` symbol is re-exported from `swork.common`.

    The three list components import from there, so removing the
    re-export would break them. Pin the import path.
    """

    def test_reexport_matches_concrete_class(self):
        assert Directory is DirectoryClass
