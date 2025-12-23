# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Registration hooks for the navigation system."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import g, request
from svcs.flask import container

from .request import NavRequest
from .tree import NavTree

if TYPE_CHECKING:
    from flask import Flask


def register_nav(app: Flask) -> None:
    """Register navigation system with Flask app.

    This function:
    1. Creates a NavTree instance bound to this app
    2. Builds the nav tree after all blueprints are registered
    3. Creates request-scoped NavRequest on each request
    4. Injects navigation data into templates via context processor
    5. Populates Context service with breadcrumbs for legacy components

    Call this AFTER registering all blueprints in your app factory.
    """
    # Create app-bound NavTree instance
    app.extensions["nav_tree"] = NavTree()

    # Build nav tree once, after first request
    # (all blueprints are registered by then)
    @app.before_request
    def build_nav_tree() -> None:
        tree = app.extensions["nav_tree"]
        if not tree._built:
            tree.build(app)

    # Create request-scoped nav state
    @app.before_request
    def setup_nav() -> None:
        endpoint = request.endpoint
        if endpoint:
            g.nav = NavRequest(endpoint, request.view_args or {})
            _inject_breadcrumbs_to_context()

    # Inject navigation into all templates
    @app.context_processor
    def inject_nav() -> dict:
        if not hasattr(g, "nav"):
            return {}

        return {
            # New nav_* variables (preferred)
            "nav_breadcrumbs": g.nav.breadcrumbs(),
            "nav_main_menu": g.nav.menu("main"),
            "nav_secondary_menu": g.nav.menu(),
            "nav_user_menu": g.nav.menu("user"),
            "nav_create_menu": g.nav.menu("create"),
        }


def _inject_breadcrumbs_to_context() -> None:
    """Inject breadcrumbs into Context service for legacy components.

    The HeaderBreadcrumbs component expects breadcrumbs in the Context service
    with keys 'name' and 'href' (legacy Page format).
    """
    if not hasattr(g, "nav"):
        return

    try:
        from app.services.context import Context

        context = container.get(Context)
        # Convert from nav format (label, url) to Page format (name, href)
        breadcrumbs = [
            {"name": crumb.label, "href": crumb.url, "current": crumb.current}
            for crumb in g.nav.breadcrumbs()
        ]
        context.update(breadcrumbs=breadcrumbs)
    except Exception:  # noqa: S110
        # Context service may not be available in all contexts (e.g., static files)
        pass
