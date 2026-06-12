# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for ``app.flask.lib.nav.registration``.

These tests exercise the navigation registration hooks against a real
lightweight Flask app (no full app factory required). Pattern A is applied
to ``_inject_breadcrumbs_to_context`` by extracting the pure conversion
``nav_crumbs_to_legacy``, which is unit-tested directly. The rest is
exercised through the real request lifecycle of a stand-up Flask app
with a real blueprint configured via ``configure_nav``.

Why this file exists:
- ``registration.py`` was at ~46% coverage; the full app fixture was
  exercising the hooks indirectly only via heavy integration paths.
- This file targets the imperative shell (before_request hooks, the
  context processor, the legacy Context bridge) with stand-up Flask
  apps so that the file is exercised mock-free.
"""

from __future__ import annotations

import sys
import types

import pytest
from flask import Blueprint, Flask, g
from svcs.flask import init_app, register_factory

from app.flask.lib.nav import registry as _registry_module
from app.flask.lib.nav.registration import (
    _inject_breadcrumbs_to_context,
    nav_crumbs_to_legacy,
    register_nav,
)
from app.flask.lib.nav.registry import configure_nav
from app.flask.lib.nav.request import NavRequest
from app.flask.lib.nav.tree import BreadCrumb, NavTree

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


class FakeContext:
    """Stand-in for ``app.services.context.Context``.

    Implements only the surface used by ``_inject_breadcrumbs_to_context``.
    """

    def __init__(self) -> None:
        self.data: dict = {}

    def update(self, **kwargs) -> None:
        self.data.update(kwargs)


def _build_app_with_blueprint(*, bp_label: str = "Events") -> Flask:
    """Build a tiny real Flask app + a blueprint with nav config."""
    app = Flask("nav_registration_test")
    bp = Blueprint("events_test_xyz", __name__, url_prefix="/events")
    configure_nav(bp, label=bp_label, icon="calendar", order=10)

    @bp.route("/")
    def index() -> str:
        """List."""
        return "ok"

    @bp.route("/<int:id>")
    def event(id: int) -> str:
        """Event."""
        return f"ok-{id}"

    app.register_blueprint(bp)
    return app


@pytest.fixture(autouse=True)
def _registry_snapshot():
    """Snapshot the global nav registry around each test.

    The registry is populated at app-module-import time (each blueprint
    calls ``configure_nav`` at import). We snapshot rather than clear so
    that we don't tear down state needed by other tests in the session.
    """
    snapshot = dict(_registry_module._NAV_REGISTRY)
    yield
    _registry_module._NAV_REGISTRY.clear()
    _registry_module._NAV_REGISTRY.update(snapshot)


# ---------------------------------------------------------------------------
# Pattern A: pure conversion
# ---------------------------------------------------------------------------


class TestNavCrumbsToLegacy:
    """Pure conversion: BreadCrumb -> legacy dict format."""

    def test_empty_input_returns_empty_list(self):
        assert nav_crumbs_to_legacy([]) == []

    def test_single_crumb(self):
        crumb = BreadCrumb(label="Home", url="/", current=True)
        result = nav_crumbs_to_legacy([crumb])
        assert result == [{"name": "Home", "href": "/", "current": True}]

    def test_multiple_crumbs_preserves_order(self):
        crumbs = [
            BreadCrumb(label="Home", url="/", current=False),
            BreadCrumb(label="Events", url="/events/", current=False),
            BreadCrumb(label="Show", url="/events/1", current=True),
        ]
        result = nav_crumbs_to_legacy(crumbs)
        assert [c["name"] for c in result] == ["Home", "Events", "Show"]
        assert [c["href"] for c in result] == ["/", "/events/", "/events/1"]
        assert [c["current"] for c in result] == [False, False, True]

    @pytest.mark.parametrize(
        ("label", "url", "current"),
        [
            ("", "/", False),
            ("Plain", "", True),
            ("Unicode événement", "/x", False),
        ],
    )
    def test_edge_values_round_trip(self, label, url, current):
        result = nav_crumbs_to_legacy(
            [BreadCrumb(label=label, url=url, current=current)]
        )
        assert result[0]["name"] == label
        assert result[0]["href"] == url
        assert result[0]["current"] is current

    def test_accepts_any_iterable(self):
        crumbs = (
            BreadCrumb(label=f"l{i}", url=f"/{i}", current=False) for i in range(3)
        )
        result = nav_crumbs_to_legacy(crumbs)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# register_nav: state effects on the Flask app
# ---------------------------------------------------------------------------


class TestRegisterNavSetup:
    """Verify ``register_nav`` produces the expected app state."""

    def test_creates_nav_tree_in_extensions(self):
        app = Flask("t")
        register_nav(app)
        assert "nav_tree" in app.extensions
        assert isinstance(app.extensions["nav_tree"], NavTree)

    def test_nav_tree_starts_unbuilt(self):
        app = Flask("t")
        register_nav(app)
        assert app.extensions["nav_tree"]._built is False

    def test_registers_two_before_request_handlers(self):
        app = Flask("t")
        before = len(app.before_request_funcs.get(None, []))
        register_nav(app)
        after = len(app.before_request_funcs.get(None, []))
        # build_nav_tree + setup_nav
        assert after - before == 2

    def test_registers_one_context_processor(self):
        app = Flask("t")
        before = len(app.template_context_processors.get(None, []))
        register_nav(app)
        after = len(app.template_context_processors.get(None, []))
        assert after - before == 1


# ---------------------------------------------------------------------------
# before_request hooks (build_nav_tree + setup_nav)
# ---------------------------------------------------------------------------


class TestBeforeRequestHooks:
    """Exercise the registered before_request hooks via a real request."""

    def test_first_request_builds_tree(self):
        app = _build_app_with_blueprint()
        register_nav(app)

        with app.test_request_context("/events/"):
            app.preprocess_request()
            assert app.extensions["nav_tree"]._built is True

    def test_request_with_known_endpoint_sets_g_nav(self):
        app = _build_app_with_blueprint()
        register_nav(app)

        with app.test_request_context("/events/"):
            app.preprocess_request()
            assert isinstance(g.nav, NavRequest)
            assert g.nav.endpoint == "events_test_xyz.index"

    def test_request_with_view_args_propagates_to_nav(self):
        app = _build_app_with_blueprint()
        register_nav(app)

        with app.test_request_context("/events/42"):
            app.preprocess_request()
            assert g.nav.endpoint == "events_test_xyz.event"
            # NavRequest stored view_args; can be observed via breadcrumbs
            crumbs = g.nav.breadcrumbs()
            assert isinstance(crumbs, list)

    def test_unknown_endpoint_skips_g_nav(self):
        app = _build_app_with_blueprint()
        register_nav(app)

        # /nope/ won't match any route -> request.endpoint is None
        with app.test_request_context("/nope/"):
            app.preprocess_request()
            assert not hasattr(g, "nav")

    def test_tree_built_once_across_two_requests(self):
        app = _build_app_with_blueprint()
        register_nav(app)

        with app.test_request_context("/events/"):
            app.preprocess_request()
            tree = app.extensions["nav_tree"]
            first_nodes = dict(tree._nodes)

        with app.test_request_context("/events/"):
            app.preprocess_request()
            assert app.extensions["nav_tree"]._nodes is first_nodes or (
                app.extensions["nav_tree"]._nodes == first_nodes
            )
            assert app.extensions["nav_tree"]._built is True


# ---------------------------------------------------------------------------
# context processor (inject_nav)
# ---------------------------------------------------------------------------


def _get_context_processor(app: Flask):
    """Return the single nav context processor registered on ``app``."""
    procs = app.template_context_processors.get(None, [])
    # The last one we appended is the nav one. App default app_context_processor
    # is index 0; nav is the most-recently-added.
    return procs[-1]


class TestContextProcessor:
    """Exercise the ``@app.context_processor`` registered by ``register_nav``."""

    def test_returns_empty_dict_when_no_g_nav(self):
        app = Flask("t")
        register_nav(app)
        cp = _get_context_processor(app)
        with app.test_request_context("/"):
            result = cp()
            assert result == {}

    def test_returns_nav_keys_when_g_nav_present(self):
        app = _build_app_with_blueprint()
        register_nav(app)
        # We do not configure svcs/Context here; the legacy bridge should
        # gracefully swallow the missing-service error.

        cp = _get_context_processor(app)
        with app.test_request_context("/events/"):
            app.preprocess_request()
            # Provide an app.settings shim for nav main_menu lookup
            result = cp()
            assert set(result.keys()) == {
                "nav_breadcrumbs",
                "nav_main_menu",
                "nav_secondary_menu",
                "nav_user_menu",
                "nav_create_menu",
            }
            assert isinstance(result["nav_breadcrumbs"], list)


# ---------------------------------------------------------------------------
# _inject_breadcrumbs_to_context
# ---------------------------------------------------------------------------


class _StubNav:
    """Stand-in for ``NavRequest`` that returns a canned breadcrumb list."""

    def __init__(self, crumbs: list[BreadCrumb]) -> None:
        self._crumbs = crumbs

    def breadcrumbs(self) -> list[BreadCrumb]:
        return self._crumbs


class TestInjectBreadcrumbsToContext:
    """Exercise the legacy Context bridge."""

    def test_returns_silently_when_no_g_nav(self):
        app = Flask("t")
        with app.test_request_context("/"):
            # No assignment to g.nav
            _inject_breadcrumbs_to_context()  # should not raise

    def test_returns_silently_when_empty_breadcrumbs(self):
        app = Flask("t")
        with app.test_request_context("/"):
            g.nav = _StubNav([])
            _inject_breadcrumbs_to_context()  # should not raise

    def test_swallows_missing_context_service(self):
        # Real svcs is not initialised on this app -> Context lookup
        # will raise; the function must swallow it.
        app = Flask("t")
        init_app(app)  # svcs installed but no Context factory registered
        with app.test_request_context("/"):
            g.nav = _StubNav([BreadCrumb("Home", "/", True)])
            _inject_breadcrumbs_to_context()  # should not raise

    def test_updates_context_when_service_registered(self):
        # Patch the Context module path to point at our fake.
        fake_module = types.ModuleType("app.services.context")

        class Context:  # real class, used as svcs key
            pass

        fake_module.Context = Context
        # If the real module is already imported, override only for this test
        # by inserting our fake before _inject_breadcrumbs_to_context's
        # local import. The local import uses sys.modules.
        original = sys.modules.get("app.services.context")
        sys.modules["app.services.context"] = fake_module
        try:
            app = Flask("t")
            init_app(app)
            fake_context = FakeContext()
            register_factory(app, Context, lambda: fake_context)

            with app.test_request_context("/"):
                g.nav = _StubNav(
                    [
                        BreadCrumb("Home", "/", False),
                        BreadCrumb("Events", "/events/", True),
                    ]
                )
                _inject_breadcrumbs_to_context()

            assert "breadcrumbs" in fake_context.data
            assert fake_context.data["breadcrumbs"] == [
                {"name": "Home", "href": "/", "current": False},
                {"name": "Events", "href": "/events/", "current": True},
            ]
        finally:
            if original is not None:
                sys.modules["app.services.context"] = original
            else:
                del sys.modules["app.services.context"]
