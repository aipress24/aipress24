# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib
import types

from attr import define, field
from flask import Blueprint
from loguru import logger

from app.lib.names import dense_fqdn, fqdn

from ._page import Page
from ._route import Route


@define
class PageRegistry:
    pages: dict[str, type[Page]] = field(factory=dict)

    def get_pages(self):
        return self.pages.values()

    def add(self, page_class):
        self.pages[fqdn(page_class)] = page_class

    def query(self, path: str = "", page_class: type | None = None) -> list[type[Page]]:
        # FIXME: marche pô.
        return self._filter_by_path(path)

    def _filter_by_path(self, path: str) -> list[type[Page]]:
        result = []
        for t in self.pages.items():
            if t[0].startswith(path):
                result.append(t[1])

        result.sort(key=lambda x: x.order)
        return result


page_registry = PageRegistry()


def get_pages():
    return page_registry.pages


def register_pages(app):
    for page_cls in page_registry.get_pages():
        blueprint = _find_blueprint(page_cls)

        logger.debug(
            "Registering page: {} on blueprint: {}",
            dense_fqdn(page_cls),
            blueprint.name,
        )

        _register_page(blueprint, page_cls)


def _find_blueprint(page_cls: type[Page]) -> Blueprint:
    module_path = page_cls.__module__.split(".")

    for i in range(len(module_path), 0, -1):
        module_name = ".".join(module_path[:i])
        module = importlib.import_module(module_name)
        if hasattr(module, "blueprint"):
            return module.blueprint

    raise RuntimeError(f"No blueprint found for page: {page_cls}")


def _register_page(blueprint: Blueprint, page_class):
    if blueprint._got_registered_once:
        return

    methods = ["GET", "POST"]

    route = Route(page_class)

    if hasattr(page_class, "routes"):
        for _route in page_class.routes:
            blueprint.add_url_rule(_route, route.endpoint, route, methods=methods)
        return

    if not hasattr(page_class, "path"):
        page_class.path = page_class.name

    blueprint.add_url_rule(page_class.path, route.endpoint, route, methods=methods)

    _register_actions(blueprint, page_class)


def _register_actions(blueprint: Blueprint, cls):
    methods = ["GET", "POST"]

    for k, v in vars(cls).items():
        if not isinstance(v, types.FunctionType):
            continue

        if not hasattr(v, "_pagic_metadata"):
            continue

        metadata = v._pagic_metadata  # type: ignore
        if metadata.get("exposed"):
            route = Route(cls, k)
            blueprint.add_url_rule(route.path, route.endpoint, route, methods=methods)
