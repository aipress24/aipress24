# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Wire main page - news feed with tabs and filters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from attr import define
from flask import redirect, render_template, request, session
from werkzeug.exceptions import NotFound

from app.flask.routing import url_for
from app.modules.wire import blueprint

if TYPE_CHECKING:
    from ._filters import FilterBar


@define
class WirePageContext:
    """Page-like object for template context."""

    label: str = "News"

    def top_news(self) -> list:
        """Return top news items (placeholder)."""
        return []


@blueprint.route("/")
def wire():
    """News - redirect to active tab."""
    from ._tabs import get_tabs

    tabs = get_tabs()
    tab = session.get("wire:tab", tabs[0].id)
    return redirect(url_for(".wire_tab", tab=tab))


@blueprint.route("/tab/<tab>")
def wire_tab(tab: str):
    """News - tab view."""
    from ._filters import FilterBar
    from ._tabs import get_tabs

    tabs = get_tabs()

    if tab not in {t.id for t in tabs}:
        raise NotFound

    session["wire:tab"] = tab
    filter_bar = FilterBar(tab)

    if "tag" in request.args:
        tag = request.args["tag"]
        filter_bar.reset()
        filter_bar.set_tag(tag)
        return redirect(url_for(".wire_tab", tab="wall"))

    if request.method == "POST":
        return _handle_post(tab, filter_bar, tabs)

    return _render_wire(tab, filter_bar, tabs)


@blueprint.route("/tab/<tab>", methods=["POST"])
def wire_tab_post(tab: str):
    """Handle filter updates via POST."""
    from ._filters import FilterBar
    from ._tabs import get_tabs

    tabs = get_tabs()

    if tab not in {t.id for t in tabs}:
        raise NotFound

    session["wire:tab"] = tab
    filter_bar = FilterBar(tab)
    filter_bar.update_state()

    posts = _get_posts(tabs, filter_bar)
    return render_template(
        "pages/wire/main.j2",
        posts=posts,
        tabs=_build_tabs(tabs),
        tab=tab,
        filter_bar=filter_bar,
    )


def _render_wire(tab: str, filter_bar: FilterBar, tabs: list):
    """Render the wire page."""
    posts = _get_posts(tabs, filter_bar)
    page = WirePageContext()

    return render_template(
        "pages/wire.j2",
        title="News",
        page=page,
        posts=posts,
        tabs=_build_tabs(tabs),
        tab=tab,
        filter_bar=filter_bar,
    )


def _handle_post(tab: str, filter_bar: FilterBar, tabs: list):
    """Handle POST request for filter updates."""
    filter_bar.update_state()
    posts = _get_posts(tabs, filter_bar)
    return render_template(
        "pages/wire/main.j2",
        posts=posts,
        tabs=_build_tabs(tabs),
        tab=tab,
        filter_bar=filter_bar,
    )


def _build_tabs(tabs: list) -> list[dict]:
    """Build tab data for template."""
    result = []
    for tab in tabs:
        tab_id = tab.id
        result.append(
            {
                "id": tab_id,
                "label": tab.label,
                "href": url_for(".wire_tab", tab=tab_id),
                "current": tab.is_active,
            }
        )
    return result


def _get_posts(tabs: list, filter_bar: FilterBar):
    """Get posts for the active tab."""
    from app.services.tagging import get_tags

    active_tab = None
    for tab in tabs:
        if tab.is_active:
            active_tab = tab
            break

    if not active_tab:
        msg = "No active tab found"
        raise RuntimeError(msg)

    posts = active_tab.get_posts(filter_bar)
    return _filter_posts_by_tag(posts, filter_bar, get_tags)


def _filter_posts_by_tag(posts, filter_bar: FilterBar, get_tags):
    """Filter posts by tag if specified."""
    if not (tag := filter_bar.tag):
        return posts

    filtered_posts = []
    for post in posts:
        tags = [t["label"] for t in get_tags(post)]
        if tag in tags:
            filtered_posts.append(post)
    return filtered_posts
