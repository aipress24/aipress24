# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib.metadata

from flask.app import Flask

from app.flask.lib.pywire import markup_component


def register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_context():
        try:
            version = importlib.metadata.version("aipress24-flask")
        except importlib.metadata.PackageNotFoundError:
            version = "???"
        return {
            "json_data": {},
            "component": markup_component,
            "app_version": version,
        }
