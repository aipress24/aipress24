# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib

from attr import define
from flask import g
from werkzeug.routing import BuildError

from app.flask.lib.pages import Page
from app.flask.routing import url_for
from app.modules.wip.constants import BLUEPRINT_NAME, MENU
from app.services.roles import has_role

__all__ = ["make_menu"]


@define
class MenuItem:
    name: str
    label: str
    icon: str
    href: str
    current: bool

    def __attrs_post_init__(self):
        assert self.href.startswith("/")


def make_menu(current_name: str):
    menu = []

    for key in MENU:
        cls = _get_class(key)

        if hasattr(cls, "allowed_roles"):
            roles = cls.allowed_roles
            if not has_role(g.user, roles):
                continue

        entry = _make_entry(cls, current_name)

        menu.append(entry)

    return menu


def _get_class(key: str) -> type[Page]:
    module_name, class_name = key.split(":")[1].rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls


def _make_entry(page_cls: type[Page], name: str) -> MenuItem:
    url = getattr(page_cls, "path", "")
    if not url.startswith("/"):
        page_name = page_cls.name
        try:
            url = url_for(f"{BLUEPRINT_NAME}.{page_name}")
        except BuildError:
            url = url_for(f"{BLUEPRINT_NAME}.{page_name}__list")

    return MenuItem(
        name=page_cls.name,
        label=page_cls.label,
        icon=page_cls.icon,
        href=url,
        current=name == page_cls.name,
    )
