# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

from starlette.applications import Starlette

from . import settings
from .admin import create_admin


def create_app():
    app = Starlette(debug=settings.DEBUG)
    create_admin(app)
    return app
