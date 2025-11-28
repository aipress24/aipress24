# Copyright (c) 2021-2024, Abilian SAS & TCA
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

        if not is_user_allowed(cls):
            continue

        entry = _make_entry(cls, current_name)

        menu.append(entry)

    return menu


def is_user_allowed(page_cls: type[Page]) -> bool:
    user = g.user

    # Check if user is authenticated
    if not user.is_authenticated:
        return False

    # Old style ACL
    if hasattr(page_cls, "allowed_roles"):
        roles = page_cls.allowed_roles
        return has_role(user, roles)

    # New style ACL (WIP)
    page = page_cls()
    acl = page.__acl__()
    if not acl:
        return True

    for line in acl:
        directive, role, _action = line
        directive = directive.lower()
        match directive:
            case "deny":
                return False
            case "allow":
                if has_role(user, role):
                    return True
            case _:
                msg = f"Invalid directive {directive} in ACL for {page_cls}"
                raise ValueError(msg)

    # False by default?
    return False


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
