# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Ref/tuto:

- https://github.com/jwbargsten/pytest-archon
- https://xebia.com/blog/how-to-tame-your-python-codebase/
"""

from __future__ import annotations

from pytest_archon import archrule


def test_models_should_not_import_flask() -> None:
    (
        archrule("models should not import flask")
        .match("app.models.*")
        .should_not_import("flask")
        .check("app")
    )

    (
        archrule("models should not import flask")
        .match("app.services.*._models")
        .should_not_import("flask")
        .check("app")
    )

    (
        archrule("models should not import flask")
        .match("app.modules.*.models")
        .should_not_import("flask")
        .check("app")
    )


def test_lib_should_not_import_flask() -> None:
    (
        archrule("lib should not import flask")
        .match("app.lib.*")
        .should_not_import("flask")
        .check("app")
    )
