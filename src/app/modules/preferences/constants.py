# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import NamedTuple


class MenuEntry(NamedTuple):
    """Menu entry configuration."""

    name: str  # Must match the view function name for "current" highlighting
    label: str
    icon: str
    endpoint: str  # Flask endpoint for url_for()


# Menu entries for the preferences module
MENU = [
    MenuEntry(
        name="profile",
        label="Visibilité du profil public",
        icon="user-circle",
        endpoint=".profile",
    ),
    MenuEntry(
        name="password",
        label="Mot de passe",
        icon="key",
        endpoint=".password",
    ),
    MenuEntry(
        name="email",
        label="Adresse email",
        icon="at-symbol",
        endpoint=".email",
    ),
    MenuEntry(
        name="invitations",
        label="Invitation d'organisation",
        icon="clipboard-document-check",
        endpoint=".invitations",
    ),
    MenuEntry(
        name="profile_page",
        label="Modification du profil",
        icon="clipboard-document-list",
        endpoint="kyc.profile_page",
    ),
    MenuEntry(
        name="interests",
        label="Centres d'intérêts",
        icon="clipboard-document-check",
        endpoint=".interests",
    ),
    MenuEntry(
        name="contact_options",
        label="Options de contact",
        icon="at-symbol",
        endpoint=".contact_options",
    ),
    MenuEntry(
        name="banner",
        label="Image de présentation",
        icon="sparkles",
        endpoint=".banner",
    ),
]
