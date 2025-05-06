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
    admin = Admin(app, engine, base_url="/db")

    kyc.register(admin)
    newsroom.register(admin)
    wire.register(admin)
