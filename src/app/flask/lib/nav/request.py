# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Request-scoped navigation state."""

from __future__ import annotations

from typing import Any

from .tree import BreadCrumb, MenuItem, get_nav_tree


class NavRequest:
    """Request-scoped navigation state.

    This is attached to `g.nav` at the start of each request.
    Views can modify label/parent to override defaults.

    Usage:
        @blueprint.route("/members/<id>")
        def member(id: str):
            user = get_obj(id, User)
            g.nav.label = user.full_name  # dynamic breadcrumb label
            return render_template(...)
    """

    def __init__(self, endpoint: str, view_args: dict[str, Any]) -> None:
        self._endpoint = endpoint
        self._view_args = view_args
        self._label_override: str | None = None
        self._parent_override: str | None = None

    @property
    def endpoint(self) -> str:
        """Get the current endpoint."""
        return self._endpoint

    @property
    def label(self) -> str | None:
        """Get the label override."""
        return self._label_override

    @label.setter
    def label(self, value: str) -> None:
        """Set dynamic breadcrumb label for current page."""
        self._label_override = value

    @property
    def parent(self) -> str | None:
        """Get the parent override."""
        return self._parent_override

    @parent.setter
    def parent(self, value: str) -> None:
        """Override inferred parent (rare)."""
        self._parent_override = value

    @property
    def current_section(self) -> str:
        """Get the section (blueprint name) for current endpoint."""
        if "." in self._endpoint:
            return self._endpoint.split(".")[0]
        return self._endpoint

    def breadcrumbs(self) -> list[BreadCrumb]:
        """Build breadcrumb trail from current endpoint to root."""
        return get_nav_tree().build_breadcrumbs(
            endpoint=self._endpoint,
            view_args=self._view_args,
            label_override=self._label_override,
            parent_override=self._parent_override,
        )

    def menu(self, section: str | None = None) -> list[MenuItem]:
        """Get menu for a section.

        Args:
            section: Section name, or None for current section.
                     Use "main" for top-level navigation.

        Returns:
            List of MenuItem objects.
        """
        if section is None:
            section = self.current_section

        return get_nav_tree().build_menu(
            section=section,
            current_endpoint=self._endpoint,
        )
