# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
TODO: merge with _components.py (???)
"""

from __future__ import annotations

import markupsafe
from attr import frozen
from flask import render_template
from jinja2 import Template
from markupsafe import Markup

from ._utils import get_template


class Component:
    class Meta:
        pass

    def __call__(self) -> markupsafe.Markup:
        context = self._get_context()
        template = self._get_template()

        # There is a type declaration error in Flask
        return Markup(render_template(template, **context))

    def _get_context(self):
        context = {}
        names = [name for name in dir(self) if not name.startswith("_")]
        for name in names:
            if name.startswith("get_"):
                context[name[4:]] = getattr(self, name)()
            elif hasattr(self, f"get_{name}"):
                context[name] = getattr(self, f"get_{name}")()
            else:
                context[name] = getattr(self, name)
        return context

    def _get_template(self) -> Template:
        return get_template(self.__class__)


@frozen
class ComponentCaller:
    component_cls: type

    def __call__(self, *args, **kwargs):
        component = self.component_cls(*args, **kwargs)
        return component()
