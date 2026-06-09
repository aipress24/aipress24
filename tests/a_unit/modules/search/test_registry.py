# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for ``app.modules.search.registry``.

The registry is the single source of truth wiring signal source types to
their indexable model class, UI sidebar entry, and doc-type
discriminators. Four call sites (``constants.COLLECTIONS``, the job
dispatcher, the rebuild CLI walk, and the adapters dispatch) all rely on
this module being internally consistent, so the contracts pinned here
include both per-entry invariants (frozen dataclass, all fields set,
non-empty UI strings, non-empty doc_types tuple) and global invariants
(no duplicate source_type / ui_name, all canonical entries present).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.biz.models import MarketplaceContent
from app.modules.events.models import EventPost
from app.modules.search.registry import (
    REGISTRY,
    IndexableType,
    lookup_by_source_type,
)
from app.modules.wire.models import ArticlePost, PressReleasePost

# Canonical source_type values shipped on 2026-05-21. Groups were
# intentionally removed; the rebuild CLI, sidebar and adapters all key
# off this exact set, so a drift here must be a deliberate registry edit.
CANONICAL_SOURCE_TYPES = frozenset(
    {"article", "press_release", "event", "marketplace", "user", "organisation"}
)


class TestIndexableTypeDataclass:
    """Pin the dataclass shape.

    ``IndexableType`` is consumed as a static descriptor by every other
    module in ``search/``. If it stops being frozen, callers could
    mutate registry entries at runtime; if a field disappears, the
    sidebar template or the rebuild walk crashes at import time. These
    tests fail loudly before either can happen.
    """

    def test_is_a_dataclass(self) -> None:
        # Other tests below rely on dataclass introspection
        # (``fields``, equality semantics). Pin the foundation first.
        assert is_dataclass(IndexableType)

    def test_is_frozen(self) -> None:
        # Frozen is load-bearing: ``REGISTRY`` is a module-level tuple
        # shared across the whole process. Mutation would be a footgun.
        entry = REGISTRY[0]
        with pytest.raises(FrozenInstanceError):
            entry.source_type = "mutated"  # type: ignore[misc]

    def test_field_set_is_exact(self) -> None:
        # Adding a field without updating the adapters / CLI would let
        # half the code paths silently ignore the new attribute. Pin the
        # exact field set so an addition has to be deliberate.
        names = {f.name for f in fields(IndexableType)}
        assert names == {
            "source_type",
            "model",
            "fk_column",
            "ui_name",
            "label",
            "icon",
            "doc_types",
        }

    def test_equality_is_value_based(self) -> None:
        # Two instances with the same fields must compare equal so
        # tests and downstream caches can rely on hash/eq semantics.
        a = IndexableType(
            source_type="x",
            model=User,
            fk_column=None,
            ui_name="x",
            label="X",
            icon="x",
            doc_types=("x",),
        )
        b = IndexableType(
            source_type="x",
            model=User,
            fk_column=None,
            ui_name="x",
            label="X",
            icon="x",
            doc_types=("x",),
        )
        assert a == b
        assert hash(a) == hash(b)

    def test_is_hashable(self) -> None:
        # Frozen dataclasses are hashable; some call sites put entries
        # into sets / dict keys, so pin this explicitly rather than rely
        # on the implicit dataclass default.
        entry = REGISTRY[0]
        assert {entry, entry} == {entry}

    def test_repr_contains_source_type(self) -> None:
        # Failing assertions in CI surface IndexableType reprs; keep the
        # source_type visible so the failure is self-describing.
        entry = IndexableType(
            source_type="probe",
            model=User,
            fk_column=None,
            ui_name="probe",
            label="Probe",
            icon="probe",
            doc_types=("probe",),
        )
        assert "probe" in repr(entry)


class TestRegistryShape:
    """Global invariants on ``REGISTRY`` as a collection."""

    def test_registry_is_a_tuple(self) -> None:
        # Tuple, not list — REGISTRY is meant to be immutable shared
        # state. A list would invite ``REGISTRY.append(...)`` somewhere.
        assert isinstance(REGISTRY, tuple)

    def test_registry_is_non_empty(self) -> None:
        # An empty registry would silently disable the whole search
        # subsystem at boot — a regression worth blocking.
        assert len(REGISTRY) > 0

    def test_every_entry_is_an_indexable_type(self) -> None:
        assert all(isinstance(entry, IndexableType) for entry in REGISTRY)

    def test_source_types_are_unique(self) -> None:
        # Duplicate source_types would make ``lookup_by_source_type``
        # non-deterministic (first-wins) and confuse receivers.
        source_types = [entry.source_type for entry in REGISTRY]
        assert len(source_types) == len(set(source_types))

    def test_ui_names_are_unique(self) -> None:
        # ui_name is the URL filter token (``?filter=articles``).
        # Duplicates would make one UI bucket unreachable.
        ui_names = [entry.ui_name for entry in REGISTRY]
        assert len(ui_names) == len(set(ui_names))

    def test_canonical_source_types_present(self) -> None:
        # Pin the actual shipping set so a silent removal (like the
        # 2026-05-21 groups removal) is visible in code review.
        actual = {entry.source_type for entry in REGISTRY}
        assert actual == CANONICAL_SOURCE_TYPES

    def test_groups_intentionally_absent(self) -> None:
        # Documented removal — pin it so a "let's just re-add groups"
        # one-line PR can't sneak through without touching this test.
        source_types = {entry.source_type for entry in REGISTRY}
        assert "group" not in source_types
        assert "groups" not in source_types


class TestRegistryEntryInvariants:
    """Per-entry contracts shared by every ``IndexableType`` in REGISTRY."""

    @pytest.mark.parametrize("entry", REGISTRY, ids=lambda e: e.source_type)
    def test_source_type_is_non_empty_string(self, entry: IndexableType) -> None:
        assert isinstance(entry.source_type, str) and entry.source_type

    @pytest.mark.parametrize("entry", REGISTRY, ids=lambda e: e.source_type)
    def test_model_is_a_class(self, entry: IndexableType) -> None:
        # ``model`` is fed to ``isinstance`` and SQLAlchemy walks in the
        # CLI; it must be a class, not an instance.
        assert isinstance(entry.model, type)

    @pytest.mark.parametrize("entry", REGISTRY, ids=lambda e: e.source_type)
    def test_fk_column_is_str_or_none(self, entry: IndexableType) -> None:
        # ``None`` means "source IS the instance, look up by PK". Any
        # other type would crash the receiver's getattr call.
        assert entry.fk_column is None or isinstance(entry.fk_column, str)

    @pytest.mark.parametrize("entry", REGISTRY, ids=lambda e: e.source_type)
    def test_ui_name_is_non_empty(self, entry: IndexableType) -> None:
        # Empty ui_name -> ``/search/?filter=`` -> matches everything.
        assert isinstance(entry.ui_name, str) and entry.ui_name

    @pytest.mark.parametrize("entry", REGISTRY, ids=lambda e: e.source_type)
    def test_label_is_non_empty(self, entry: IndexableType) -> None:
        # Empty label -> blank sidebar row.
        assert isinstance(entry.label, str) and entry.label

    @pytest.mark.parametrize("entry", REGISTRY, ids=lambda e: e.source_type)
    def test_icon_is_non_empty(self, entry: IndexableType) -> None:
        # Empty icon -> sidebar template falls back to a broken heroicon
        # path. The collection name proxy the spec mentions.
        assert isinstance(entry.icon, str) and entry.icon

    @pytest.mark.parametrize("entry", REGISTRY, ids=lambda e: e.source_type)
    def test_doc_types_is_non_empty_tuple_of_strings(
        self, entry: IndexableType
    ) -> None:
        # doc_types feeds the search-result bucketing query; empty would
        # make the bucket invisible. Tuple (not list) keeps it hashable.
        assert isinstance(entry.doc_types, tuple)
        assert len(entry.doc_types) > 0
        assert all(isinstance(d, str) and d for d in entry.doc_types)

    def test_doc_types_are_globally_unique(self) -> None:
        # A given doc_type discriminator must map to exactly one UI
        # bucket — otherwise a single document would surface in two
        # sidebar entries.
        all_doc_types: list[str] = []
        for entry in REGISTRY:
            all_doc_types.extend(entry.doc_types)
        assert len(all_doc_types) == len(set(all_doc_types))


class TestCanonicalEntries:
    """Pin the concrete wiring of the canonical entries.

    The receivers and the rebuild CLI hard-code these source_type
    strings; if the model class or fk_column changes the corresponding
    domain signal silently stops re-indexing. Tests here document the
    intended wiring.
    """

    @pytest.mark.parametrize(
        ("source_type", "expected_model", "expected_fk"),
        [
            ("article", ArticlePost, "newsroom_id"),
            ("press_release", PressReleasePost, "newsroom_id"),
            ("event", EventPost, "eventroom_id"),
            ("marketplace", MarketplaceContent, None),
            ("user", User, None),
            ("organisation", Organisation, None),
        ],
    )
    def test_entry_wiring(
        self,
        source_type: str,
        expected_model: type,
        expected_fk: str | None,
    ) -> None:
        entry = lookup_by_source_type(source_type)
        assert entry.model is expected_model
        assert entry.fk_column == expected_fk

    def test_marketplace_bucket_has_four_subtypes(self) -> None:
        # Marketplace is the only polymorphic UI bucket — pin its four
        # subtypes since the adapters singledispatch surface assumes
        # exactly this set.
        entry = lookup_by_source_type("marketplace")
        assert set(entry.doc_types) == {
            "mission_offer",
            "project_offer",
            "job_offer",
            "editorial_product",
        }

    @pytest.mark.parametrize(
        "source_type",
        ["article", "press_release", "event", "user", "organisation"],
    )
    def test_single_doc_type_matches_source_type(self, source_type: str) -> None:
        # Non-polymorphic buckets ship a single doc_type that equals the
        # source_type. The adapters dispatch relies on that convention.
        entry = lookup_by_source_type(source_type)
        assert entry.doc_types == (source_type,)


class TestLookupBySourceType:
    """Behaviour of the public lookup helper."""

    @pytest.mark.parametrize("source_type", sorted(CANONICAL_SOURCE_TYPES))
    def test_known_source_type_returns_entry(self, source_type: str) -> None:
        entry = lookup_by_source_type(source_type)
        assert isinstance(entry, IndexableType)
        assert entry.source_type == source_type

    def test_lookup_returns_the_registry_instance(self) -> None:
        # Identity, not just equality — receivers compare ``is`` in
        # some hot paths, so the helper must hand back the singleton.
        entry = lookup_by_source_type("article")
        assert any(entry is r for r in REGISTRY)

    def test_unknown_source_type_raises_key_error(self) -> None:
        # The docstring explicitly says "miss is a programming error
        # worth surfacing" — pin KeyError, not None.
        with pytest.raises(KeyError):
            lookup_by_source_type("does_not_exist")

    def test_key_error_message_quotes_the_input(self) -> None:
        # The receiver / job dispatcher catches and logs; the offending
        # value must be visible in the message to debug bad signals.
        with pytest.raises(KeyError) as excinfo:
            lookup_by_source_type("bogus")
        assert "bogus" in str(excinfo.value)

    @pytest.mark.parametrize("bad_input", ["", "ARTICLE", "article ", " article"])
    def test_lookup_is_case_and_whitespace_sensitive(self, bad_input: str) -> None:
        # The match is a plain ``==`` against a string field. Pin this
        # so nobody "helpfully" adds .strip().lower() — receivers send
        # canonical lowercase tokens and any normalisation would mask
        # a real bug in the emitter.
        with pytest.raises(KeyError):
            lookup_by_source_type(bad_input)
