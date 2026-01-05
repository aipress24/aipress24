# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Navigation configuration registry.

Provides a clean way to attach navigation metadata to Flask blueprints
without monkey-patching or subclassing.

Usage:
    from flask import Blueprint
    from app.flask.lib.nav import configure_nav

    blueprint = Blueprint("events", __name__, url_prefix="/events")
    configure_nav(
        blueprint,
        label="Events",
        icon="calendar",
        order=30,
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from flask import Blueprint


class NavConfig(TypedDict, total=False):
    """Navigation configuration for a blueprint section.

    Attributes:
        label: Display label in menus/breadcrumbs
        icon: Icon name (e.g., "calendar", "users")
        order: Sort order in menus (lower = first)
        acl: Access control rules [(action, role, permission), ...]
        in_menu: Whether to show in main navigation menu
    """

    label: str
    icon: str
    order: int
    acl: list[tuple[str, Any, str]]
    in_menu: bool


# Global registry: blueprint_name -> NavConfig
_NAV_REGISTRY: dict[str, NavConfig] = {}


def configure_nav(
    blueprint: Blueprint,
    *,
    label: str,
    icon: str = "",
    order: int = 99,
    acl: list[tuple[str, Any, str]] | None = None,
    in_menu: bool = True,
) -> None:
    """Register navigation configuration for a blueprint.

    Args:
        blueprint: The Flask blueprint to configure
        label: Display label in menus/breadcrumbs
        icon: Icon name (e.g., "calendar", "users")
        order: Sort order in menus (lower = first, default 99)
        acl: Access control rules [(action, role, permission), ...]
        in_menu: Whether to show in main navigation menu (default True)

    Example:
        blueprint = Blueprint("events", __name__, url_prefix="/events")
        configure_nav(blueprint, label="Events", icon="calendar", order=30)
    """
    config: NavConfig = {
        "label": label,
        "icon": icon,
        "order": order,
        "in_menu": in_menu,
    }
    if acl is not None:
        config["acl"] = acl

    _NAV_REGISTRY[blueprint.name] = config


def get_nav_config(blueprint_name: str) -> NavConfig | None:
    """Get navigation configuration for a blueprint by name.

    Args:
        blueprint_name: The name of the blueprint

    Returns:
        NavConfig if registered, None otherwise
    """
    return _NAV_REGISTRY.get(blueprint_name)


def clear_registry() -> None:
    """Clear the navigation registry. Useful for testing."""
    _NAV_REGISTRY.clear()
