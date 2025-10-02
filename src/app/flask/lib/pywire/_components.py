# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import inspect
import json
import uuid
from pathlib import Path
from typing import ClassVar

from flask import current_app, render_template
from jinja2 import Environment, Template

from app.lib.names import to_kebab_case

from ._utils import get_template

component_registry: dict[str, type] = {}


class StaticComponent:
    _id: str
    _template: str = ""

    def __init__(self, id: str = "") -> None:
        if id:
            self._id = id
        else:
            self._id = uuid.uuid4().hex

    def mount(self, **kwargs) -> None:
        self._restore(kwargs)

    def _restore(self, state) -> None:
        for k, v in state.items():
            setattr(self, k, v)

    # Override this method to return the initial data
    def context(self):
        return {}

    # May be ovverriden
    def render(self) -> str:
        return self.render_template()

    # May be ovverriden
    def render_template(self) -> str:
        ctx = self.context()

        if self._template:
            return self._template.format(self=self, ctx=ctx)

        template: Template = self._get_template()
        return render_template(template, this=self, **ctx)

    @property
    def _name(self) -> str:
        return self.__class__._get_name()

    @classmethod
    def _get_name(cls) -> str:
        return to_kebab_case(cls.__name__)

    def _get_template(self) -> Template:
        template_name = self._name.replace("-", "_") + ".j2"
        template_file = Path(inspect.getfile(self.__class__)).parent / template_name
        jinja_env: Environment = current_app.jinja_env
        return jinja_env.from_string(template_file.read_text())

    def _initial_render(self) -> str:
        return self.render()


class WiredComponent:
    _id: str
    # _name: str

    _attrs: ClassVar[list[str]] = []
    _template: str = ""
    _listeners: ClassVar[list[str]] = []

    def __init__(self, id: str = "") -> None:
        if id:
            self._id = id
        else:
            self._id = uuid.uuid4().hex

    def mount(self, **kwargs) -> None:
        self._restore(kwargs)

    def _restore(self, state) -> None:
        for k, v in state.items():
            setattr(self, k, v)

    # Override this method to return the initial data
    def context(self):
        return {}

    # May be ovverriden
    def render(self) -> str:
        return self.render_template()

    # May be ovverriden
    def render_template(self) -> str:
        ctx = self.context()

        if self._template:
            return self._template.format(self=self, ctx=ctx)

        template: Template = self._get_template()
        return render_template(template, this=self, **ctx)

    def _initial_render(self) -> str:
        initial_data = json.dumps(self._initial_data(), indent=2)
        initial_data = initial_data.replace("'", "\\u0027")

        markup = self.render()
        return markup.replace(
            "wire:id",
            f"wire:initial-data='{initial_data}' wire:id",
        )

    def _initial_markup(self) -> str:
        initial_data = json.dumps(self._initial_data())

        markup = self.render()
        markup = markup.replace(
            "wire:id",
            f"wire:initial-data='{initial_data}' wire:id",
        )
        return markup

    def _initial_data(self):
        return {
            "fingerprint": {
                "id": self._id,
                "name": self._name,
                "locale": "en",
                "path": "/",
                "method": "GET",
                "v": "acj",
            },
            "effects": {
                "listeners": self._listeners,
            },
            "serverMemo": {
                "children": [],
                "errors": [],
                "htmlHash": "2ce01892",
                "data": self._state(),
                "dataMeta": [],
                "checksum": (
                    "a28b0e2cf4e538e24ff4a4dd6495f255b65c11ebfa986254a1cb80cf3d36d129"
                ),
            },
        }

    def _state(self):
        return {k: getattr(self, k) for k in self._attrs}

    @property
    def _dirty(self) -> list[str]:
        return self._attrs

    @property
    def _name(self) -> str:
        return self.__class__._get_name()

    @classmethod
    def _get_name(cls) -> str:
        return to_kebab_case(cls.__name__)

    def _get_template(self) -> Template:
        return get_template(self.__class__)
