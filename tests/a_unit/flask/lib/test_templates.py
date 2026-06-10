# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.flask.lib.templates`.

The module exposes three pieces of machinery worth covering at the unit
level:

1. `resolve_template_path` - a pure path resolver introduced via
   Pattern A (functional-core extraction). It computes the on-disk
   template path for an object using `inspect.getfile`, with a
   special-case for object instances that need the class fallback.

2. `enrich_context` (module-level) - a pure version of the OpenGraph
   wiring done by `TemplateResponse.enrich_context`. Pattern B lets us
   inject stand-in `to_opengraph_fn` / `to_json_ld_fn` collaborators
   instead of relying on Flask globals or singledispatch registrations.

3. `templated` - the decorator wrapping the view function.

All tests follow the project rule: no mocks; only real stubs/fakes,
verifying state.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from flask import Flask, Response

from app.flask.lib.templates import (
    TemplateResponse,
    enrich_context,
    resolve_template_path,
    templated,
)

# --------------------------------------------------------------------- #
# Stubs                                                                 #
# --------------------------------------------------------------------- #


class _StubModel:
    """Plain object used as the `model` value inside contexts."""

    def __init__(self, name: str = "hello") -> None:
        self.name = name


class _StubWrapped:
    """Mimics the `view_model.Wrapper` protocol used by `unwrap`.

    `unwrap` looks for the `_model` attribute; we set it explicitly
    rather than using `attrs` (which strips the leading underscore).
    """

    def __init__(self, model: object) -> None:
        self._model = model


def _fake_to_opengraph(model: object) -> dict:
    return {"og:title": getattr(model, "name", "no-name")}


def _fake_to_json_ld(model: object) -> dict:
    return {"@type": "Thing", "name": getattr(model, "name", "no-name")}


# --------------------------------------------------------------------- #
# resolve_template_path                                                  #
# --------------------------------------------------------------------- #


class TestResolveTemplatePath:
    """The pure resolver should mirror `inspect.getfile` semantics."""

    def test_with_path_uses_module_directory(self) -> None:
        # A module object: getfile returns the file directly.
        result = resolve_template_path(inspect, "templates/form.j2")
        expected_dir = Path(inspect.__file__).parent
        assert result == expected_dir / "templates/form.j2"

    def test_empty_path_swaps_extension_to_j2(self) -> None:
        result = resolve_template_path(inspect, "")
        assert result == Path(inspect.__file__).with_suffix(".j2")

    def test_instance_falls_back_to_class(self) -> None:
        # `inspect.getfile` raises TypeError on a bare instance; the
        # resolver must transparently use the class location instead.
        obj = _StubModel()
        result = resolve_template_path(obj, "form.j2")
        expected_dir = Path(inspect.getfile(_StubModel)).parent
        assert result == expected_dir / "form.j2"

    def test_instance_empty_path(self) -> None:
        obj = _StubModel()
        result = resolve_template_path(obj, "")
        expected = Path(inspect.getfile(_StubModel)).with_suffix(".j2")
        assert result == expected

    @pytest.mark.parametrize(
        "rel_path",
        [
            "a.j2",
            "sub/dir/x.j2",
            "./local.j2",
        ],
    )
    def test_various_subpaths(self, rel_path: str) -> None:
        result = resolve_template_path(inspect, rel_path)
        expected = Path(inspect.__file__).parent / rel_path
        assert result == expected


# --------------------------------------------------------------------- #
# enrich_context                                                        #
# --------------------------------------------------------------------- #


class TestEnrichContext:
    """`enrich_context` is the pure form of the OG wiring."""

    def test_none_context_yields_empty_with_json_data(self) -> None:
        result = enrich_context(None)
        assert result == {"json_data": {}}

    def test_empty_context_adds_json_data(self) -> None:
        result = enrich_context({})
        assert result == {"json_data": {}}

    def test_preserves_existing_json_data(self) -> None:
        result = enrich_context({"json_data": {"x": 1}})
        assert result == {"json_data": {"x": 1}}

    def test_does_not_mutate_input(self) -> None:
        ctx = {"foo": "bar"}
        enrich_context(ctx)
        assert ctx == {"foo": "bar"}

    def test_model_triggers_og_and_jsonld_injection(self) -> None:
        model = _StubModel(name="hello")
        result = enrich_context(
            {"model": model},
            to_opengraph_fn=_fake_to_opengraph,
            to_json_ld_fn=_fake_to_json_ld,
        )
        assert result["og_data"] == {"og:title": "hello"}
        assert result["json_ld"] == {"@type": "Thing", "name": "hello"}
        assert result["model"] is not model  # deepcopy copies the model
        assert result["model"].name == "hello"
        assert result["json_data"] == {}

    def test_unwraps_wrapped_model_before_serialising(self) -> None:
        # `unwrap` looks for `_model`; the OG fn should receive the
        # underlying model, not the wrapper.
        seen: list[object] = []

        def og(obj):
            seen.append(obj)
            return {"og:title": obj.name}

        def jld(obj):
            return {"name": obj.name}

        inner = _StubModel(name="wrapped")
        wrapped = _StubWrapped(model=inner)
        result = enrich_context(
            {"model": wrapped},
            to_opengraph_fn=og,
            to_json_ld_fn=jld,
        )
        assert len(seen) == 1
        assert getattr(seen[0], "name", None) == "wrapped"
        assert result["og_data"] == {"og:title": "wrapped"}

    def test_no_model_means_no_og_keys(self) -> None:
        result = enrich_context(
            {"foo": "bar"},
            to_opengraph_fn=_fake_to_opengraph,
            to_json_ld_fn=_fake_to_json_ld,
        )
        assert "og_data" not in result
        assert "json_ld" not in result
        assert result["foo"] == "bar"
        assert result["json_data"] == {}

    def test_defaults_to_production_collaborators(self) -> None:
        # Without injection, the function should use real defaults. We
        # cannot exercise the real `to_opengraph` on a stub without
        # extra wiring (it calls Flask `url_for`), but we *can* check
        # that the default `to_json_ld` is invoked: it looks for a
        # `to_json_ld` method on the model. We provide one to drive
        # the production path without leaving the unit boundary.
        class ModelWithJsonLd:
            name = "z"

            def to_json_ld(self):
                return {"@id": "z"}

        # Inject a fake OG fn but leave json-ld defaulted to exercise
        # the production default.
        result = enrich_context(
            {"model": ModelWithJsonLd()},
            to_opengraph_fn=_fake_to_opengraph,
        )
        assert result["json_ld"] == {"@id": "z"}


# --------------------------------------------------------------------- #
# TemplateResponse                                                      #
# --------------------------------------------------------------------- #


@pytest.fixture
def flask_app() -> Flask:
    """Minimal Flask app for rendering responses."""
    app = Flask(__name__)
    return app


class TestTemplateResponse:
    """`TemplateResponse` glues `enrich_context` with Flask rendering."""

    def test_render_template_string(self, flask_app: Flask) -> None:
        with flask_app.app_context():
            resp = TemplateResponse({"name": "world"}, "Hello {{ name }}!")
        assert isinstance(resp, Response)
        assert resp.get_data(as_text=True) == "Hello world!"

    def test_context_enriched_with_json_data(self, flask_app: Flask) -> None:
        with flask_app.app_context():
            resp = TemplateResponse({}, "x")
        assert resp.context == {"json_data": {}}

    def test_unknown_template_type_raises_value_error(
        self, flask_app: Flask
    ) -> None:
        with flask_app.app_context():
            with pytest.raises(ValueError):
                TemplateResponse({}, template=12345)  # type: ignore[arg-type]

    def test_method_enrich_context_uses_module_function(
        self, flask_app: Flask
    ) -> None:
        # The bound method `enrich_context` should delegate to the
        # module-level `enrich_context` and accept the same DI kwargs.
        with flask_app.app_context():
            resp = TemplateResponse({}, "x")
        out = resp.enrich_context(
            {"model": _StubModel("m")},
            to_opengraph_fn=_fake_to_opengraph,
            to_json_ld_fn=_fake_to_json_ld,
        )
        assert out["og_data"] == {"og:title": "m"}
        assert out["json_ld"] == {"@type": "Thing", "name": "m"}


# --------------------------------------------------------------------- #
# templated decorator                                                   #
# --------------------------------------------------------------------- #


class TestTemplatedDecorator:
    """`templated` wraps a view function; if the view already returns a
    `Response`, that response should pass through untouched."""

    def test_passthrough_when_view_returns_response(
        self, flask_app: Flask
    ) -> None:
        sentinel = Response("already-rendered", status=201)

        @templated("ignored")
        def view():
            return sentinel

        with flask_app.app_context():
            result = view()
        assert result is sentinel
        assert result.status_code == 201

    def test_wraps_dict_into_template_response(
        self, flask_app: Flask
    ) -> None:
        @templated("Hi {{ name }}!")
        def view():
            return {"name": "claude"}

        with flask_app.app_context():
            result = view()
        assert isinstance(result, TemplateResponse)
        assert result.get_data(as_text=True) == "Hi claude!"

    def test_wrapper_forwards_args_and_kwargs(
        self, flask_app: Flask
    ) -> None:
        @templated("{{ x }}-{{ y }}")
        def view(x, *, y):
            return {"x": x, "y": y}

        with flask_app.app_context():
            result = view("a", y="b")
        assert result.get_data(as_text=True) == "a-b"
