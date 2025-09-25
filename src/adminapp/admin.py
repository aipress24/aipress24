"""Admin interface setup and configuration."""

# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

from sqladmin import Admin
from sqlalchemy.ext.asyncio import create_async_engine

from . import settings
from .views import kyc, newsroom, wire

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
)


def create_admin(app) -> None:
    """Create and configure the admin interface.

    Args:
        app: Starlette application instance to attach admin to.
    """
    admin = Admin(app, engine, base_url="/db")

    kyc.register(admin)
    newsroom.register(admin)
    wire.register(admin)
