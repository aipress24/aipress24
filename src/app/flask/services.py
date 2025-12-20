"""Service registration and dependency injection setup."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from inspect import signature

import svcs
from flask import Flask
from flask_super.registry import lookup
from sqlalchemy.orm import scoped_session
from svcs.flask import register_factory

__all__ = [
    "register_services",
]


def session_factory() -> scoped_session:
    from app.flask.extensions import db

    return db.session


def register_services(app: Flask) -> None:
    register_factory(app, scoped_session, session_factory)

    services = lookup(tag="service")

    assert all(isinstance(service, type) for service in services)

    for cls_or_factory in services:
        if factory := getattr(cls_or_factory, "svcs_factory", None):
            register_factory(app, cls_or_factory, factory)

        elif isinstance(cls_or_factory, type):
            cls = cls_or_factory
            svcs.flask.register_factory(app, cls, cls)

        else:
            factory = cls_or_factory
            sig = signature(factory)
            cls = sig.return_annotation
            svcs.flask.register_factory(app, cls, factory)
