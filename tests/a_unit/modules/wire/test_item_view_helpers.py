# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for pure helpers in wire.views.item.

The article / press-release detail view (`ItemDetailView`) is the
classic mixed-concerns Flask `MethodView` : an HTTP shell wrapped
around several pure pieces. We exercise those pieces directly so the
unit tier carries the regression weight :

- `post_type_label(...)` is a pure mapping from a polymorphic
  identity string to a French display label (`Article`, `Communiqué`,
  `Non classé`). Extracted from the nested `post_type()` closure
  inside `_get_metadata_list` so it no longer needs a Post.
- `build_metadata_list(...)` is the `[{label, value}]` builder for
  the side-panel. We pass plain duck-typed `SimpleNamespace` stand-
  ins and route the two KYC ontology lookups through injected
  callables (Pattern B) so no ontology files have to load.
- `_get_comment_object_id(...)` is a pure dispatch on the post
  subclass — `ArticlePost -> "article:<id>"`, `PressReleasePost ->
  "press-release:<id>"`, fallback `"post:<id>"`.

The DB-backed `get()` / `post()` handlers, the `record_view` write,
and the rights-policy / article-access calls all live in the
b_integration tier; this file deliberately stays mock-free.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.wire.models import ArticlePost, Post, PressReleasePost
from app.modules.wire.views.item import (
    _get_comment_object_id,
    build_metadata_list,
    post_type_label,
)


def _stub_post(
    *,
    type: str | None = "article",
    genre: str = "",
    section: str = "",
    topic: str = "",
    sector: str = "",
    address: str = "",
    pays_zip_ville: str = "",
    pays_zip_ville_detail: str = "",
) -> SimpleNamespace:
    """Duck-typed Post stand-in.

    `build_metadata_list` only reads attributes (`.type`, `.genre`,
    ...) so a plain `SimpleNamespace` is enough — no ORM, no DB, no
    polymorphic loader.
    """
    return SimpleNamespace(
        type=type,
        genre=genre,
        section=section,
        topic=topic,
        sector=sector,
        address=address,
        pays_zip_ville=pays_zip_ville,
        pays_zip_ville_detail=pays_zip_ville_detail,
    )


def _entry(data: list[dict], label: str) -> dict | None:
    """Find the first {label, value} dict matching `label`."""
    for item in data:
        if item["label"] == label:
            return item
    return None


def _value(data: list[dict], label: str) -> object:
    """Return the value for a label, asserting it exists.

    Convenience wrapper so type-checkers don't flag subscripting an
    `Optional[dict]` returned by `_entry`.
    """
    entry = _entry(data, label)
    assert entry is not None, f"missing label {label!r} in {data!r}"
    return entry["value"]


def _labels(data: list[dict]) -> list[str]:
    """Return the ordered list of labels in a metadata list."""
    return [item["label"] for item in data]


class TestPostTypeLabel:
    """`post_type_label` maps a polymorphic identity to a French
    display string."""

    @pytest.mark.parametrize(
        ("type_str", "expected"),
        [
            ("article", "Article"),
            ("press_release", "Communiqué"),
        ],
    )
    def test_known_types_return_french_label(self, type_str, expected):
        assert post_type_label(type_str) == expected

    @pytest.mark.parametrize(
        "type_str",
        ["post", "unknown", "ARTICLE", "Article", "video"],
    )
    def test_unknown_types_fall_back_to_non_classe(self, type_str):
        assert post_type_label(type_str) == "Non classé"

    @pytest.mark.parametrize("type_str", [None, ""])
    def test_missing_type_falls_back_to_non_classe(self, type_str):
        assert post_type_label(type_str) == "Non classé"

    def test_lookup_is_pure_and_repeatable(self):
        # Calling twice with the same input must yield identical
        # output — guards against accidental mutation of the module-
        # level dispatch table.
        assert post_type_label("article") == post_type_label("article")
        assert post_type_label("article") == "Article"


class TestBuildMetadataListCore:
    """Core five rows are always present, in deterministic order."""

    def test_minimal_post_has_five_core_rows(self):
        post = _stub_post(type="article")
        data = build_metadata_list(post)
        assert _labels(data) == [
            "Type",
            "Genre",
            "Rubrique",
            "Sujet",
            "Secteur d'activité",
        ]

    def test_blank_optional_fields_render_as_na(self):
        post = _stub_post(type="article")
        data = build_metadata_list(post)
        for label in ("Genre", "Rubrique", "Sujet", "Secteur d'activité"):
            assert _value(data, label) == "N/A"

    def test_filled_optional_fields_render_their_value(self):
        post = _stub_post(
            type="article",
            genre="Reportage",
            section="Tech",
            topic="IA",
            sector="Média",
        )
        data = build_metadata_list(post)
        assert _value(data, "Genre") == "Reportage"
        assert _value(data, "Rubrique") == "Tech"
        assert _value(data, "Sujet") == "IA"
        assert _value(data, "Secteur d'activité") == "Média"

    @pytest.mark.parametrize(
        ("type_str", "expected"),
        [
            ("article", "Article"),
            ("press_release", "Communiqué"),
            ("post", "Non classé"),
            (None, "Non classé"),
        ],
    )
    def test_type_row_uses_post_type_label(self, type_str, expected):
        post = _stub_post(type=type_str)
        data = build_metadata_list(post)
        assert _value(data, "Type") == expected


class TestBuildMetadataListOptionalRows:
    """Address / Pays / Ville rows appear only when populated."""

    def test_no_optional_rows_when_blank(self):
        post = _stub_post(type="article")
        labels = _labels(build_metadata_list(post))
        assert "Adresse" not in labels
        assert "Pays" not in labels
        assert "Ville" not in labels

    def test_address_appears_when_set(self):
        post = _stub_post(type="article", address="12 rue de Rivoli")
        data = build_metadata_list(post)
        assert _value(data, "Adresse") == "12 rue de Rivoli"

    def test_pays_uses_injected_country_lookup(self):
        # Pattern B : stub the ontology lookup so the test stays
        # offline. Verify the *returned* dict, not whether the stub
        # was called (state, not behavior).
        post = _stub_post(type="article", pays_zip_ville="FR")
        data = build_metadata_list(
            post,
            country_label=lambda code: f"<country:{code}>",
        )
        assert _value(data, "Pays") == "<country:FR>"

    def test_ville_uses_injected_city_lookup(self):
        post = _stub_post(
            type="article",
            pays_zip_ville_detail='FR / "75001 Paris"',
        )
        data = build_metadata_list(
            post,
            city_label=lambda code: f"<city:{code}>",
        )
        assert _value(data, "Ville") == '<city:FR / "75001 Paris">'

    def test_all_optional_rows_appear_in_order(self):
        post = _stub_post(
            type="press_release",
            address="1 Infinite Loop",
            pays_zip_ville="US",
            pays_zip_ville_detail='US / "95014 Cupertino"',
        )
        data = build_metadata_list(
            post,
            country_label=lambda code: f"country({code})",
            city_label=lambda code: f"city({code})",
        )
        # Core rows first, then Adresse, Pays, Ville in that order.
        assert _labels(data) == [
            "Type",
            "Genre",
            "Rubrique",
            "Sujet",
            "Secteur d'activité",
            "Adresse",
            "Pays",
            "Ville",
        ]

    def test_pays_does_not_call_lookup_when_blank(self):
        # If `pays_zip_ville` is empty, the country row must not
        # appear *and* the injected callable must not be invoked.
        # A lookup that raises proves we never reach it.
        msg_country = "country_label called for blank pays_zip_ville"

        def exploding(_code: str) -> str:
            raise AssertionError(msg_country)

        post = _stub_post(type="article")
        data = build_metadata_list(post, country_label=exploding)
        assert _entry(data, "Pays") is None

    def test_ville_does_not_call_lookup_when_blank(self):
        msg_city = "city_label called for blank pays_zip_ville_detail"

        def exploding(_code: str) -> str:
            raise AssertionError(msg_city)

        post = _stub_post(type="article")
        data = build_metadata_list(post, city_label=exploding)
        assert _entry(data, "Ville") is None

    def test_default_lookups_are_not_invoked_when_blank(self):
        # Smoke check that the production defaults are wired in :
        # because the optional fields are blank, the real
        # `country_code_to_label` / `country_zip_code_to_city` are
        # never called, so this stays a pure unit test.
        post = _stub_post(type="article")
        data = build_metadata_list(post)
        assert "Pays" not in _labels(data)
        assert "Ville" not in _labels(data)


class TestGetCommentObjectId:
    """`_get_comment_object_id` dispatches on the Post subclass."""

    def test_article_post_yields_article_prefix(self):
        post = ArticlePost()
        post.id = 42
        assert _get_comment_object_id(post) == "article:42"

    def test_press_release_post_yields_press_release_prefix(self):
        post = PressReleasePost()
        post.id = 7
        assert _get_comment_object_id(post) == "press-release:7"

    def test_bare_post_falls_back_to_post_prefix(self):
        # The base `Post` is the catch-all branch of the match.
        post = Post()
        post.id = 99
        assert _get_comment_object_id(post) == "post:99"

    @pytest.mark.parametrize(
        ("cls", "post_id", "expected"),
        [
            (ArticlePost, 1, "article:1"),
            (ArticlePost, 12345, "article:12345"),
            (PressReleasePost, 1, "press-release:1"),
            (PressReleasePost, 999, "press-release:999"),
        ],
    )
    def test_id_round_trips_through_the_match(self, cls, post_id, expected):
        post = cls()
        post.id = post_id
        assert _get_comment_object_id(post) == expected

    def test_match_is_stable_across_calls(self):
        # Pure function — two calls on the same input return the
        # same string.
        post = ArticlePost()
        post.id = 5
        assert _get_comment_object_id(post) == _get_comment_object_id(post)
