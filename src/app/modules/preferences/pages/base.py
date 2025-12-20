# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc

__all__ = ("BasePreferencesPage",)


class BasePreferencesPage(abc.ABC):
    """Base class for preferences page metadata.

    Note: This class is kept for backwards compatibility with tests.
    The actual page rendering is done by Flask views, not Page classes.
    """

    name: str
    label: str
    icon: str
    template: str = ""
    path: str = ""
    parent: type | None = None
    url_string: str = ""

    @property
    def title(self):
        return self.label

    def menus(self):
        from ._menu import make_menu

        return {
            "secondary": make_menu(self.name),
        }
