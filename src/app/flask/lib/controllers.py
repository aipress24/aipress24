# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import inspect
from pathlib import Path

from attr import define


class Controller:
    name: str
    path: str
    meta: Meta


@define
class Dispatcher:
    cls: type[Controller]
    method_name: str

    __name__ = "Dispatcher"

    def __call__(self, *args, **kwargs):
        obj = self.cls()
        method = getattr(obj, self.method_name)
        return method(*args, **kwargs)


@define
class Meta:
    cls: type[Controller]

    def register_on(self, blueprint):
        def predicate(obj):
            return inspect.isfunction(obj) and hasattr(obj, "_meta")

        methods = inspect.getmembers(self.cls, predicate)

        for _name, method in methods:
            self.register_method(blueprint, method)

    def register_method(self, blueprint, method):
        meta = method._meta
        path = self.cls.path + meta["path"]
        methods = meta["methods"]
        name = self.cls.name + "__" + method.__name__
        dispatcher = Dispatcher(self.cls, method.__name__)
        blueprint.add_url_rule(path, name, dispatcher, methods=methods)

    def get_template(self):
        file = inspect.getfile(self.cls)
        path = Path(file)
        template = path.with_suffix(".j2")
        return template.read_text()


#
# Decorators
#
def controller(cls):
    cls.meta = Meta(cls)
    return cls


def get(path: str):
    assert path.startswith("/")

    def decorator(func):
        func._meta = {"path": path, "methods": ["GET"]}
        return func

    return decorator


def post(path: str):
    assert path.startswith("/")

    def decorator(func):
        func._meta = {"path": path, "methods": ["POST"]}
        return func

    return decorator


def route(path: str, methods: list[str]):
    assert path.startswith("/")

    def decorator(func):
        func._meta = {"path": path, "methods": methods}
        return func

    return decorator
