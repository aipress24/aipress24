# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import NamedTuple


class MenuEntry(NamedTuple):
    """Menu entry configuration."""

    name: str
    label: str
    icon: str
    endpoint: str
    allowed_roles: list[str] | None = None


# Menu entries for the WIP module
# Format: (name, label, icon, endpoint, allowed_roles)
MENU = [
    MenuEntry(
        name="dashboard",
        label="Tableau de bord",
        icon="chart-bar",
        endpoint="wip.dashboard",
        allowed_roles=["PRESS_MEDIA", "ACADEMIC"],
    ),
    MenuEntry(
        name="newsroom",
        label="Newsroom",
        icon="rocket-launch",
        endpoint="wip.newsroom",
        allowed_roles=["PRESS_MEDIA"],
    ),
    MenuEntry(
        name="comroom",
        label="Com'room",
        icon="megaphone",
        endpoint="wip.comroom",
        allowed_roles=["PRESS_RELATIONS"],
    ),
    MenuEntry(
        name="eventroom",
        label="Event'room",
        icon="calendar",
        endpoint="wip.eventroom",
    ),
    MenuEntry(
        name="opportunities",
        label="Opportunités",
        icon="cake",
        endpoint="wip.opportunities",
    ),
    MenuEntry(
        name="org-profile",
        label="Business Wall",
        icon="building-library",
        endpoint="wip.org-profile",
    ),
    MenuEntry(
        name="bw-activation",
        label="New Business Wall",
        icon="building-library",
        endpoint="bw_activation.index",
    ),
    MenuEntry(
        name="billing",
        label="Facturation",
        icon="credit-card",
        endpoint="wip.billing",
    ),
    MenuEntry(
        name="performance",
        label="Performance",
        icon="star",
        endpoint="wip.performance",
    ),
]

BLUEPRINT_NAME = "wip"
