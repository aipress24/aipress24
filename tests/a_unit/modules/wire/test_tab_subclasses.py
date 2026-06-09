# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the concrete Tab subclasses in `wire/views/_tabs.py`.

These tests pin down the per-subclass contract of the wire feed tabs
(WallTab, AgenciesTab, MediasTab, JournalistsTab, ComTab). The existing
test_tabs.py file only verifies the `get_tabs()` ordering, a smoke check
that the required attributes exist, plus the post-type allowlists for
WallTab and ComTab. Every other subclass-specific value -- French labels,
URL slugs, tooltip strings, post-type sets for the three middle tabs,
slug uniqueness, and the Tab base-class lineage -- is unpinned and could
silently drift. This file closes that gap.

Why each cluster of tests exists:

* Label / id / tip literals are user-facing (URL slugs in `id`, French UI
  copy in `label` and `tip`). They must not silently change on refactor;
  doing so breaks bookmarks, screen-reader output, and translations.
* `post_type_allow` controls which Post types each tab queries. A typo
  ("articles" instead of "article", "press_release" vs "pressrelease")
  would silently empty a tab. We pin the exact set membership and
  intentionally cover the *new* tabs (AgenciesTab, MediasTab,
  JournalistsTab) that the existing file omits.
* Slug uniqueness is a defensive cross-cutting invariant: two tabs with
  the same `id` would corrupt `Tab.is_active` (it reads `session["wire:
  tab"] == self.id`) and the URL routing.
* The base-class lineage check guarantees every subclass picks up the
  shared `get_stmt` / `get_posts` machinery; if someone accidentally
  drops the `Tab` parent the subclass would still "work" but lose the
  filter / sort behaviour.
* Instantiability proves no subclass leaves an abstract method
  unimplemented (the base inherits from `abc.ABC`).
"""

from __future__ import annotations

import abc

import pytest

from app.modules.wire.views._tabs import (
    AgenciesTab,
    ComTab,
    JournalistsTab,
    MediasTab,
    Tab,
    WallTab,
)

# All five concrete Tab subclasses, in the canonical order returned by
# `get_tabs()`. Centralising the list keeps parametrize tables aligned.
ALL_TAB_CLASSES = [WallTab, AgenciesTab, MediasTab, JournalistsTab, ComTab]


class TestTabIdentifiers:
    """Pin the URL slug (`id`) of every concrete Tab subclass.

    Slugs leak into URLs and the wire session key (`session["wire:tab"]`),
    so any drift is an externally visible breaking change.
    """

    @pytest.mark.parametrize(
        ("tab_cls", "expected_id"),
        [
            (WallTab, "wall"),
            (AgenciesTab, "agencies"),
            (MediasTab, "media"),
            (JournalistsTab, "journalists"),
            (ComTab, "com"),
        ],
    )
    def test_id_literal(self, tab_cls: type[Tab], expected_id: str) -> None:
        # Class-level access proves the literal is a static contract,
        # not the result of __init__ assignment.
        assert tab_cls.id == expected_id
        # Instance access must match -- guards against a property override.
        assert tab_cls().id == expected_id

    def test_ids_are_unique_across_subclasses(self) -> None:
        """No two tabs may share an id, else session/routing collapse."""
        ids = [cls.id for cls in ALL_TAB_CLASSES]
        assert len(ids) == len(set(ids)), f"Duplicate tab ids detected: {ids}"

    def test_ids_are_non_empty_lowercase_slugs(self) -> None:
        """Defensive: slugs must be URL-safe ascii lowercase."""
        for cls in ALL_TAB_CLASSES:
            assert cls.id, f"{cls.__name__}.id is empty"
            assert cls.id == cls.id.lower(), (
                f"{cls.__name__}.id={cls.id!r} must be lowercase"
            )
            assert cls.id.isascii(), f"{cls.__name__}.id={cls.id!r} must be ascii"


class TestTabLabels:
    """Pin the French UI label of every concrete Tab subclass.

    Labels are translated copy; silent edits regress the UI. WallTab's
    label is the English placeholder "All" -- intentionally left as-is
    by the codebase, so we pin that too.
    """

    @pytest.mark.parametrize(
        ("tab_cls", "expected_label"),
        [
            (WallTab, "All"),
            (AgenciesTab, "Agences"),
            (MediasTab, "Médias"),
            (JournalistsTab, "Journalistes"),
            (ComTab, "Idées & Comm"),
        ],
    )
    def test_label_literal(self, tab_cls: type[Tab], expected_label: str) -> None:
        assert tab_cls.label == expected_label
        assert tab_cls().label == expected_label

    def test_labels_are_unique(self) -> None:
        """Two tabs with the same label confuse users; defensive."""
        labels = [cls.label for cls in ALL_TAB_CLASSES]
        assert len(labels) == len(set(labels)), f"Duplicate tab labels: {labels}"


class TestTabTooltips:
    """Pin the French tooltip (`tip`) of every concrete Tab subclass."""

    @pytest.mark.parametrize(
        ("tab_cls", "expected_tip"),
        [
            (WallTab, "Fil d'actus"),
            (AgenciesTab, "Agences de Presse"),
            (MediasTab, "Médias (presse, en ligne...) auxquels je suis abonné"),
            (JournalistsTab, "Les journalistes que je suis"),
            (ComTab, "Communiqués de presse"),
        ],
    )
    def test_tip_literal(self, tab_cls: type[Tab], expected_tip: str) -> None:
        assert tab_cls.tip == expected_tip
        assert tab_cls().tip == expected_tip


class TestTabPostTypeAllow:
    """Pin the `post_type_allow` set for the subclasses NOT already covered.

    `test_tabs.py::test_wall_and_com_tab_post_types` already pins WallTab
    and ComTab, so we deliberately omit them here to avoid duplication.
    The three middle tabs all share the same `{"article", "post"}` set,
    which is a deliberate product decision -- if any of them diverges, a
    feed silently changes shape.
    """

    @pytest.mark.parametrize(
        "tab_cls",
        [AgenciesTab, MediasTab, JournalistsTab],
    )
    def test_post_type_allow_is_article_and_post(self, tab_cls: type[Tab]) -> None:
        assert tab_cls.post_type_allow == {"article", "post"}
        # Defensive: must be a *set*, not a list/tuple, because the
        # base class feeds it to `Post.type.in_(...)`.
        assert isinstance(tab_cls.post_type_allow, set)

    def test_com_tab_post_type_is_isolated(self) -> None:
        """ComTab must NOT bleed regular posts into press releases."""
        assert "article" not in ComTab.post_type_allow
        assert "post" not in ComTab.post_type_allow


class TestTabInheritance:
    """The shared query / sort machinery lives on `Tab` -- subclasses
    must inherit it. A subclass that accidentally lost the base would
    still "work" but skip filtering, sorting, and limiting."""

    @pytest.mark.parametrize("tab_cls", ALL_TAB_CLASSES)
    def test_subclass_inherits_from_tab(self, tab_cls: type[Tab]) -> None:
        assert issubclass(tab_cls, Tab)

    def test_tab_base_is_abstract(self) -> None:
        """Sanity: Tab is declared with abc.ABC, even though no method
        is marked abstract today. Future maintainers may add abstract
        methods; this assertion documents the intent so it doesn't get
        silently converted to a plain class."""
        assert issubclass(Tab, abc.ABC)

    @pytest.mark.parametrize("tab_cls", ALL_TAB_CLASSES)
    def test_subclass_can_be_instantiated(self, tab_cls: type[Tab]) -> None:
        """Each subclass implements every abstract method (currently
        none) and has no __init__ requiring arguments."""
        instance = tab_cls()
        assert isinstance(instance, Tab)


class TestTabGetAuthorsDefault:
    """`Tab.get_authors` defaults to returning an empty iterable.

    WallTab overrides it to explicitly return `[]` -- the existing
    test_tabs.py pins that. The three other tabs that override it
    (Agencies / Medias / Journalists) hit Flask `g.user`, so they
    can't be invoked in a pure unit test. ComTab does NOT override
    it, so it must fall through to the base default; pin that here."""

    def test_com_tab_uses_base_default(self) -> None:
        # The base default returns an empty list, so ComTab inherits
        # exactly that -- no filter by author for press releases.
        assert ComTab().get_authors() == []

    def test_com_tab_does_not_override_get_authors(self) -> None:
        """Defensive: ComTab.get_authors must be the inherited method,
        not a subclass override, so changes to the base propagate."""
        assert ComTab.get_authors is Tab.get_authors
