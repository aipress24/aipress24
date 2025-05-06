# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

import threading

import granian
from asgiref.wsgi import WsgiToAsgi
from granian.constants import Interfaces, Loops
from granian.log import LogLevels
from starlette.applications import Starlette
from starlette.config import Config
from starlette.routing import Mount

from adminapp.main import create_app as create_admin_app
from app.flask.main import create_app as create_flask_app
from server.scheduler import scheduler

config = Config()

PORT = config("PORT", cast=int, default=5000)
DEBUG = config("FLASK_DEBUG", cast=bool, default=False)
if DEBUG:
    LOG_LEVEL = LogLevels.debug
else:
    LOG_LEVEL = LogLevels.info


def create_app():
    flask_app = WsgiToAsgi(create_flask_app())
    admin_app = create_admin_app()

    app = Starlette(
        routes=[
            Mount("/db/", app=admin_app),
            Mount("/", app=flask_app),
        ]
    )
    return app


def serve(port: int = PORT, debug: bool = DEBUG, log_level: LogLevels = LOG_LEVEL) -> None:
    print("debug:", debug)

    scheduler_thread = threading.Thread(target=scheduler)
    scheduler_thread.start()

    reload = debug
    granian.Granian(
        target="server.main:create_app",
        factory=True,
        address="0.0.0.0",  # noqa: S104
        port=port,
        interface=Interfaces.ASGI,
        log_dictconfig={"root": {"level": "INFO"}} if not debug else {},
        log_level=log_level,
        loop=Loops.uvloop,
        reload=reload,
    ).serve()
