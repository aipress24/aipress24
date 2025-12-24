# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Navigation tree built from Flask routes at startup."""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from flask import g, url_for
from loguru import logger

if TYPE_CHECKING:
    from flask import Flask

    from app.models.auth import User


@dataclass
class NavNode:
    """A node in the navigation tree."""

    name: str  # endpoint name (e.g., "events.event")
    label: str  # display label
    url_rule: str  # URL pattern (e.g., "/<int:id>")
    parent: str | None = None  # parent endpoint name
    icon: str = ""
    order: int = 99
    acl: list[tuple[str, Any, str]] = field(default_factory=list)
    inherited_acl: list[tuple[str, Any, str]] = field(default_factory=list)
    acl_source: str | None = None  # Where ACL was inherited from (None = own)
    in_menu: bool = True
    is_section: bool = False  # True for blueprint roots

    @property
    def effective_acl(self) -> list[tuple[str, Any, str]]:
        """Get effective ACL (own or inherited)."""
        return self.acl if self.acl else self.inherited_acl

    def url_for(self, **kwargs: Any) -> str:
        """Generate URL for this node."""
        try:
            # Filter kwargs to only include params in this URL
            relevant_kwargs = {
                k: v
                for k, v in kwargs.items()
                if f"<{k}>" in self.url_rule or f"<int:{k}>" in self.url_rule
            }
            # Section nodes don't have endpoints - use the URL rule directly
            if self.is_section:
                return self.url_rule
            return url_for(self.name, **relevant_kwargs)
        except Exception:
            return "#"

    def is_visible_to(self, user: User) -> bool:
        """Check if user can see this node based on ACL (own or inherited).

        Magic roles are handled specially:
        - SELF: Visible to any authenticated user (ownership checked in view)
        """
        acl = self.effective_acl
        if not acl:
            return True

        from app.enums import RoleEnum
        from app.services.roles import has_role

        for directive, role, _action in acl:
            directive_lower = directive.lower()
            if directive_lower == "deny":
                return False
            if directive_lower == "allow":
                # Handle SELF magic role: visible to any authenticated user
                if role == RoleEnum.SELF:
                    if not getattr(user, "is_anonymous", True):
                        return True
                elif has_role(user, role):
                    return True

        # If we had ACL rules but none matched, deny by default
        return False


@dataclass(frozen=True)
class BreadCrumb:
    """A breadcrumb entry."""

    label: str
    url: str
    current: bool = False


@dataclass
class MenuItem:
    """A menu item."""

    label: str
    url: str
    icon: str = ""
    active: bool = False
    tooltip: str = ""


class NavTree:
    """Navigation tree, built at app startup from routes.

    Each Flask app has its own NavTree instance stored in app.extensions.
    Use get_nav_tree() to access the tree for the current app.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, NavNode] = {}
        self._sections: dict[str, NavNode] = {}
        self._url_to_endpoint: dict[str, str] = {}
        self._built = False

    def build(self, app: Flask) -> None:
        """Scan blueprints and routes, build navigation tree."""
        if self._built:
            return

        self._build_sections(app)
        self._build_pages(app)
        self._build_url_index()
        self._propagate_acl()
        self._validate()
        self._built = True

        logger.debug("Nav tree built with {} nodes", len(self._nodes))

    def _build_sections(self, app: Flask) -> None:
        """Build section nodes from blueprints with .nav attribute."""
        for name, bp in app.blueprints.items():
            nav_config = getattr(bp, "nav", None)
            if nav_config is None:
                continue

            node = NavNode(
                name=name,
                label=nav_config.get("label", name.title()),
                url_rule=bp.url_prefix or "/",
                icon=nav_config.get("icon", ""),
                order=nav_config.get("order", 99),
                acl=nav_config.get("acl", []),
                is_section=True,
            )
            self._nodes[name] = node
            self._sections[name] = node

            logger.debug("Nav section: {} -> {}", name, node.label)

    def _build_pages(self, app: Flask) -> None:
        """Build page nodes from routes."""
        for rule in app.url_map.iter_rules():
            endpoint = rule.endpoint

            # Skip non-blueprint endpoints
            if "." not in endpoint:
                continue

            # Skip static endpoints
            if endpoint.startswith("static") or ".static" in endpoint:
                continue

            section = endpoint.split(".")[0]

            # Only process routes for blueprints with nav config
            if section not in self._sections:
                continue

            view_func = app.view_functions.get(endpoint)
            if view_func is None:
                continue

            meta = getattr(view_func, "_nav_meta", {})

            # Skip hidden routes
            if meta.get("hidden"):
                continue

            # Skip if already registered (multiple routes same endpoint)
            if endpoint in self._nodes:
                continue

            parent = self._infer_parent(rule.rule, section, meta.get("parent"))
            label = self._infer_label(view_func, meta.get("label"))

            node = NavNode(
                name=endpoint,
                label=label,
                url_rule=rule.rule,
                parent=parent,
                icon=meta.get("icon", ""),
                order=meta.get("order", 99),
                acl=meta.get("acl", []),
                in_menu=meta.get("menu", True),
            )
            self._nodes[endpoint] = node

            logger.debug(
                "Nav page: {} -> {} (parent: {})", endpoint, node.label, node.parent
            )

    def _build_url_index(self) -> None:
        """Build reverse index from URL patterns to endpoints."""
        for endpoint, node in self._nodes.items():
            # Normalize URL for matching
            normalized = self._normalize_url(node.url_rule)
            self._url_to_endpoint[normalized] = endpoint

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for parent matching."""
        # Remove type converters: <int:id> -> <id>
        normalized = re.sub(r"<\w+:(\w+)>", r"<\1>", url)
        # Ensure trailing slash for consistency
        if not normalized.endswith("/") and "<" not in normalized.split("/")[-1]:
            normalized += "/"
        return normalized

    def _infer_parent(
        self, url_rule: str, section: str, override: str | None
    ) -> str | None:
        """Infer parent from URL pattern."""
        if override:
            # If override matches section name, point to section directly
            if override == section:
                return section
            # If override doesn't contain a dot, prepend section
            if "." not in override:
                return f"{section}.{override}"
            return override

        # Normalize and split URL
        normalized = self._normalize_url(url_rule)
        parts = [p for p in normalized.split("/") if p]

        if len(parts) <= 1:
            # Top-level page in section (e.g., /events/)
            return section

        # Try to find parent by removing last segment
        # /events/123 -> /events/ -> events.events
        # /events/calendar/ -> /events/ -> events.events

        # Remove last segment
        if parts[-1].startswith("<"):
            # URL param: /events/<id> -> /events/
            parent_parts = parts[:-1]
        else:
            # Static segment: /events/calendar/ -> /events/
            parent_parts = parts[:-1]

        if not parent_parts:
            return section

        # Build parent URL and look it up
        parent_url = "/" + "/".join(parent_parts) + "/"
        parent_endpoint = self._url_to_endpoint.get(parent_url)

        if parent_endpoint:
            return parent_endpoint

        # Fallback: section root
        return section

    def _infer_label(self, view_func: Any, override: str | None) -> str:
        """Infer label from docstring or function name."""
        if override:
            return override

        # Try docstring first line
        if view_func.__doc__:
            first_line = view_func.__doc__.strip().split("\n")[0]
            if first_line:
                return first_line

        # Fallback to function name, titleized
        name = view_func.__name__
        return name.replace("_", " ").title()

    def _validate(self) -> None:
        """Warn about potential issues."""
        for name, node in self._nodes.items():
            if node.is_section:
                continue

            if node.parent and node.parent not in self._nodes:
                warnings.warn(
                    f"Nav: {name} has parent '{node.parent}' which doesn't exist",
                    stacklevel=2,
                )

    def _propagate_acl(self) -> None:
        """Propagate ACL from sections/parents to children without own ACL.

        This allows setting ACL once on a section (e.g., admin) and having
        all child routes inherit it automatically.
        """
        for name, node in self._nodes.items():
            if node.is_section:
                continue

            # Skip nodes that have their own ACL
            if node.acl:
                continue

            # Find ACL to inherit by walking up the parent chain
            inherited_acl, source = self._find_inherited_acl(node)
            if inherited_acl:
                node.inherited_acl = inherited_acl
                node.acl_source = source
                logger.debug(
                    "Nav ACL inherited: {} <- {} ({})",
                    name,
                    source,
                    [
                        r[1].name if hasattr(r[1], "name") else r[1]
                        for r in inherited_acl
                    ],
                )

    def _find_inherited_acl(
        self, node: NavNode
    ) -> tuple[list[tuple[str, Any, str]], str | None]:
        """Walk up parent chain to find ACL to inherit."""
        visited = {node.name}  # Prevent cycles
        current_name = node.parent

        while current_name:
            if current_name in visited:
                break
            visited.add(current_name)

            parent_node = self._nodes.get(current_name)
            if not parent_node:
                break

            # Found ACL - return it with source
            if parent_node.acl:
                return parent_node.acl, current_name

            # Continue up the chain
            current_name = parent_node.parent

        return [], None

    def get(self, endpoint: str) -> NavNode | None:
        """Get a node by endpoint name."""
        return self._nodes.get(endpoint)

    def children_of(self, parent: str) -> list[NavNode]:
        """Get direct children of a node that should appear in menus."""
        children = [
            node
            for node in self._nodes.values()
            if node.parent == parent and node.in_menu and not node.is_section
        ]
        return sorted(children, key=lambda n: (n.order or 99, n.label or ""))

    def build_breadcrumbs(
        self,
        endpoint: str,
        view_args: dict[str, Any],
        label_override: str | None = None,
        parent_override: str | None = None,
    ) -> list[BreadCrumb]:
        """Build breadcrumb trail from endpoint to root."""
        crumbs: list[BreadCrumb] = []

        node = self.get(endpoint)
        if not node:
            return crumbs

        # Current page
        label = label_override or node.label
        url = node.url_for(**view_args)
        crumbs.append(BreadCrumb(label=label, url=url, current=True))

        # Walk up parent chain
        parent_name = parent_override or node.parent
        visited = {endpoint}  # Prevent infinite loops

        while parent_name and parent_name not in visited:
            visited.add(parent_name)
            parent_node = self.get(parent_name)
            if not parent_node:
                break

            crumbs.append(
                BreadCrumb(
                    label=parent_node.label,
                    url=parent_node.url_for(**view_args),
                    current=False,
                )
            )

            parent_name = parent_node.parent

        return list(reversed(crumbs))

    def build_menu(
        self,
        section: str,
        current_endpoint: str,
    ) -> list[MenuItem]:
        """Build menu for a section.

        Args:
            section: Menu type - "main", "user", "create", or a blueprint name
            current_endpoint: Current request endpoint for active state

        Returns:
            List of MenuItem objects
        """
        user = getattr(g, "user", None)

        # Main menu = list of sections
        if section == "main":
            return self._build_main_menu(current_endpoint, user)

        # Static menus (user dropdown, create action menu, admin)
        if section in ("user", "create", "admin"):
            return self._build_static_menu(section, user, current_endpoint)

        # Section submenu (blueprint secondary menu)
        children = self.children_of(section)
        items = []

        for node in children:
            if user and not node.is_visible_to(user):
                continue

            items.append(
                MenuItem(
                    label=node.label,
                    url=node.url_for(),
                    icon=node.icon,
                    active=self._is_active(node.name, current_endpoint),
                )
            )

        return items

    def _build_main_menu(
        self, current_endpoint: str, user: User | None
    ) -> list[MenuItem]:
        """Build main navigation from MAIN_MENU config."""
        from app.settings.menus import MAIN_MENU

        items = []

        for entry in MAIN_MENU:
            endpoint = entry.get("endpoint", "#")

            # Check if current endpoint is in this section
            section = endpoint.split(".")[0] if "." in endpoint else endpoint
            is_active = (
                current_endpoint.startswith(section + ".")
                or current_endpoint == section
            )

            try:
                item_url = url_for(endpoint)
            except Exception:
                item_url = "#"

            items.append(
                MenuItem(
                    label=entry.get("label", ""),
                    url=item_url,
                    icon=entry.get("icon", ""),
                    active=is_active,
                    tooltip=entry.get("tooltip", ""),
                )
            )

        return items

    def _build_static_menu(
        self, menu_name: str, user: User | None, current_endpoint: str = ""
    ) -> list[MenuItem]:
        """Build menu from static configuration.

        Args:
            menu_name: "user", "create", or "admin"
            user: Current user for ACL filtering
            current_endpoint: Current request endpoint for active state

        Returns:
            List of MenuItem objects
        """
        from app.services.roles import has_role
        from app.settings.menus import ADMIN_MENU, CREATE_MENU, USER_MENU

        config = {"user": USER_MENU, "create": CREATE_MENU, "admin": ADMIN_MENU}.get(
            menu_name, []
        )
        items = []

        for entry in config:
            # Check role-based access
            roles = entry.get("roles", set())
            if roles and user:
                if not any(has_role(user, role) for role in roles):
                    continue
            elif roles and not user:
                # Roles required but no user
                continue

            # Build URL from endpoint
            endpoint = entry.get("endpoint", "#")
            if endpoint.startswith("/"):
                # Direct URL
                item_url = endpoint
                is_active = False
            elif endpoint == "#":
                item_url = "#"
                is_active = False
            else:
                try:
                    item_url = url_for(endpoint)
                    is_active = endpoint == current_endpoint
                except Exception:
                    item_url = "#"
                    is_active = False

            items.append(
                MenuItem(
                    label=entry.get("label", ""),
                    url=item_url,
                    icon=entry.get("icon", ""),
                    active=is_active,
                )
            )

        return items

    def _is_active(self, node_endpoint: str, current_endpoint: str) -> bool:
        """Check if node is in current breadcrumb trail."""
        if node_endpoint == current_endpoint:
            return True

        # Check if current is a descendant
        node = self.get(current_endpoint)
        while node and node.parent:
            if node.parent == node_endpoint:
                return True
            node = self.get(node.parent)

        return False


def get_nav_tree() -> NavTree:
    """Get the NavTree for the current Flask app.

    The NavTree is stored in app.extensions['nav_tree'] and created
    by register_nav() during app initialization.

    Returns:
        The NavTree instance for the current app.

    Raises:
        RuntimeError: If called outside of application context or
            if nav system hasn't been registered.
    """
    from flask import current_app

    if "nav_tree" not in current_app.extensions:
        msg = (
            "NavTree not initialized. Call register_nav(app) during app initialization."
        )
        raise RuntimeError(msg)

    return current_app.extensions["nav_tree"]
