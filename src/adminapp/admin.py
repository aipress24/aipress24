from sqladmin import Admin
from sqlalchemy.ext.asyncio import create_async_engine

from . import settings
from .views import kyc, newsroom, wire

engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
)


def create_admin(app):
    admin = Admin(app, engine)

    kyc.register(admin)
    newsroom.register(admin)
    wire.register(admin)
