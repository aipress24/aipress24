# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Convention-driven navigation system for Flask.

This module provides automatic navigation (breadcrumbs, menus) derived from
routes, requiring minimal configuration.

Usage:
    # In blueprint __init__.py
    blueprint.nav = {
        "label": "Events",
        "icon": "calendar",
        "order": 3,
    }

    # In views (most pages need nothing)
    @blueprint.route("/events/")
    def events():
        '''Evénements'''
        return render_template("pages/events.j2")

    # For dynamic labels
    @blueprint.route("/events/<int:id>")
    def event(id: int):
        event = get_obj(id, EventPost)
        g.nav.label = event.title
        return render_template("pages/event.j2", event=event)

    # For overrides
    @blueprint.route("/my-events/")
    @nav(parent="events", icon="star")
    def my_events():
        '''Mes événements'''
        return render_template("pages/my_events.j2")
"""

from __future__ import annotations

from .decorator import nav
from .registration import register_nav
from .tree import NavTree, get_nav_tree

__all__ = ["NavTree", "get_nav_tree", "nav", "register_nav"]
