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
        label="Work",
        icon="chart-pie",
        endpoint="wip.dashboard",
        allowed_roles=["PRESS_MEDIA", "ACADEMIC"],
    ),
    MenuEntry(
        name="newsroom",
        label="Newsroom",
        icon="newspaper",
        endpoint="wip.newsroom",
        allowed_roles=["PRESS_MEDIA", "ACADEMIC"],
    ),
    MenuEntry(
        name="comroom",
        label="Comroom",
        icon="megaphone",
        endpoint="wip.comroom",
        allowed_roles=["PR_COM"],
    ),
    MenuEntry(
        name="eventroom",
        label="Eventroom",
        icon="calendar-days",
        endpoint="wip.eventroom",
        allowed_roles=["PRESS_MEDIA", "ACADEMIC", "PR_COM", "EXPERTS", "TRANSFORMER"],
    ),
    MenuEntry(
        name="opportunities",
        label="Opportunités",
        icon="bolt",
        endpoint="wip.opportunities",
    ),
    MenuEntry(
        name="org-profile",
        label="Business Wall",
        icon="building-library",
        endpoint="wip.org-profile",
    ),
    MenuEntry(
        name="billing",
        label="Achats & Facturation",
        icon="credit-card",
        endpoint="wip.billing",
    ),
    MenuEntry(
        name="performance",
        label="Performance",
        icon="chart-bar",
        endpoint="wip.performance",
    ),
]

BLUEPRINT_NAME = "wip"
