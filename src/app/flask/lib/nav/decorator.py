# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Navigation decorator for overriding inferred defaults."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def nav(  # noqa: PLR0913
    *,
    parent: str | None = None,
    label: str | None = None,
    icon: str | None = None,
    order: int | None = None,
    acl: list[tuple[str, Any, str]] | None = None,
    menu: bool = True,
    hidden: bool = False,
) -> Callable:
    """Decorator to override navigation defaults for a view.

    Most views need no decorator - navigation is inferred from:
    - Parent: URL hierarchy
    - Label: First line of docstring, or function name titleized

    Use this decorator only when you need to override these defaults.

    Args:
        parent: Override inferred parent endpoint (e.g., "events" for events.event).
                Can be relative (within same blueprint) or absolute.
        label: Static label (instead of docstring/function name).
        icon: Icon identifier for menus.
        order: Position in menu (lower = earlier). Default is 99.
        acl: Access control list for visibility. List of (directive, role, action)
             tuples, e.g., [("Allow", RoleEnum.ADMIN, "view")].
        menu: If False, page has breadcrumbs but doesn't appear in menus.
        hidden: If True, page is excluded from navigation entirely (no breadcrumbs,
                no menu). Use for API endpoints, redirects, etc.

    Example:
        @blueprint.route("/my-profile/")
        @nav(parent="members", menu=False)
        def my_profile():
            '''Mon profil'''
            return redirect(...)

        @blueprint.route("/admin/")
        @nav(acl=[("Allow", "admin", "view")])
        def admin_panel():
            '''Administration'''
            return render_template(...)
    """

    def decorator(f: Callable) -> Callable:
        f._nav_meta = {  # type: ignore[attr-defined]
            "parent": parent,
            "label": label,
            "icon": icon,
            "order": order,
            "acl": acl or [],
            "menu": menu,
            "hidden": hidden,
        }
        return f

    return decorator
