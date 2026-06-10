# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.flask.lib.pywire._markup.markup_component`.

`markup_component` is the Jinja `component(name, *a, **kw)` global.
It dispatches across two registries :

1. `component_registry` (`_components.py`) — string-keyed, used by the
   older `StaticComponent` / `WiredComponent` flow. Hit by exact name ;
   instantiates the class, calls `mount(...)`, then `_initial_render()`.
2. `COMPONENTS` (`_registry.py`) — class-set, used by the newer
   `Component` (`_components2.py`) flow. Scanned by `to_kebab_case(cls.__name__)`
   match ; instantiates via `ComponentCaller`.
3. Fallback : log + return Markup with `[unknown component <name>]`.

These tests cover the not-found fallback and the registry-1 path
(success + exception). Registry-2's happy path needs a colocated
template file on disk (`get_template(cls)`) which is integration
territory ; the kebab-case lookup miss is covered indirectly via
the not-found fallback.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from markupsafe import Markup

from app.flask.lib.pywire._components import component_registry
from app.flask.lib.pywire._markup import markup_component


@pytest.fixture
def fresh_registry() -> Iterator[dict]:
    """Tests mutate `component_registry` ; restore it on teardown so
    we don't leak fake classes to other tests."""
    snapshot = dict(component_registry)
    try:
        yield component_registry
    finally:
        component_registry.clear()
        component_registry.update(snapshot)


class _StubComponent:
    """Minimal duck-typed component : satisfies `mount(*a, **kw)` +
    `_initial_render() -> str`. The registry-1 branch only calls
    these two — anything else is YAGNI."""

    def __init__(self) -> None:
        self.mounted_with: tuple = ()
        self.mounted_kwargs: dict = {}

    def mount(self, *args, **kwargs) -> None:
        self.mounted_with = args
        self.mounted_kwargs = kwargs

    def _initial_render(self) -> str:
        return f"<x args={self.mounted_with!r} kw={self.mounted_kwargs!r}/>"


class _ExplodingComponent:
    def __init__(self) -> None:
        pass

    def mount(self, *args, **kwargs) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    def _initial_render(self) -> str:  # pragma: no cover - never reached
        return ""


class TestMarkupComponentNotFound:
    def test_unknown_name_returns_escaped_placeholder(self) -> None:
        """The fallback HTML-escapes the name and wraps it in Markup —
        not in HTML chars or a 500. Pin the contract."""
        result = markup_component("absolutely-no-such-component")

        assert isinstance(result, Markup)
        assert "[unknown component absolutely-no-such-component]" in result

    def test_unknown_name_with_html_chars_is_escaped(self) -> None:
        """A name carrying angle brackets must not let HTML through —
        otherwise we'd have an XSS vector via the Jinja `component()`
        global."""
        result = markup_component("<script>alert(1)</script>")

        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestMarkupComponentLegacyRegistry:
    """Registry-1 path : `component_registry[name]` lookup."""

    def test_registered_component_is_mounted_with_args_and_rendered(
        self, fresh_registry
    ) -> None:
        fresh_registry["greeter"] = _StubComponent

        result = markup_component("greeter", "hello", lang="fr")

        assert isinstance(result, Markup)
        assert "args=('hello',)" in result
        assert "lang" in result and "fr" in result

    def test_mount_kwargs_propagate_via_render(self, fresh_registry) -> None:
        fresh_registry["greeter"] = _StubComponent

        result = markup_component("greeter", user="alice")

        assert "user" in result and "alice" in result

    def test_no_args_is_supported(self, fresh_registry) -> None:
        fresh_registry["greeter"] = _StubComponent

        result = markup_component("greeter")

        assert isinstance(result, Markup)
        assert "args=()" in result

    def test_exception_during_render_returns_markup_error(
        self, fresh_registry
    ) -> None:
        """A failing component must not propagate the exception (would
        500 the whole Jinja render). The fallback returns Markup with
        the exception message — visible but not load-bearing on the
        rest of the page."""
        fresh_registry["broken"] = _ExplodingComponent

        result = markup_component("broken")

        assert isinstance(result, Markup)
        assert "Error rendering component broken" in result
        assert "boom" in result
