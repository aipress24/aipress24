# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import os
import time

import stripe
import svcs
from devtools import debug
from flask import Flask, Response, g, request, session
from flask_super import register_commands
from flask_super.registry import lookup
from flask_super.scanner import scan_packages
from loguru import logger
from werkzeug.utils import find_modules, import_string

from app.flask import debugging, services
from app.flask.config import setup_config
from app.flask.extensions import register_extensions
from app.flask.hooks import register_hooks
from app.flask.jinja import register_context_processors
from app.flask.lib.macros import register_macros
from app.flask.lib.pages import register_pages
from app.flask.lib.pywire import (
    register_components,
    register_pywire,
    register_wired_components,
)
from app.flask.security import register_oauth_providers
from app.services.stripe.products import (
    check_stripe_public_key,
    check_stripe_secret_key,
)
from app.ui.labels import make_label

# Where we're looking for blueprints
MODULES = "app.modules"

# All modules and packages that should be scanned for side effects
# (e.g. registering callbacks, service, etc.)
SCAN_PACKAGES = [
    "app",
]

MAX_REQUEST_DURATION = 0.5

debugging.install()


def create_app(config=None) -> Flask:
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app = svcs.flask.init_app(app)

    # 1: set up app.config properly
    setup_config(app, config)

    # 2: Scan to pre-register callbacks, services, etc.
    scan_packages(SCAN_PACKAGES)

    # 3. Perform registrations on app
    register_all(app)

    # 4. Bootstrap data if needed
    # bootstrap_data(app)

    return app


def register_all(app: Flask) -> None:
    # Extensions
    register_extensions(app)
    register_stripe(app)

    # Register CLI commands
    register_commands(app)

    # Register services on the svcs container
    services.register_services(app)

    # Register Jinja, etc.
    register_filters(app)
    register_macros(app)
    register_perf_watcher(app)
    register_context_processors(app)
    register_components(app)
    register_wired_components(app)

    # Request lifecycle
    register_hooks(app)
    register_debug_hooks(app)

    # Register pages & blueprints (last)
    register_pages(app)
    register_blueprints(app)
    register_extra_apps(app)
    register_pywire(app)
    register_everything_else(app)

    # Not used (yet?)
    register_oauth_providers(app)

    # Local imports bc import cycles
    from app.dramatiq.setup import init_dramatiq

    init_dramatiq(app)

    if not check_stripe_secret_key(app):
        debug("STRIPE_SECRET_KEY not found in config")

    if not check_stripe_public_key(app):
        debug("STRIPE_PUBLIC_KEY not found in config")


def register_debug_hooks(app: Flask) -> None:
    if not app.config.get("DEBUG_CONFIG"):
        return

    @app.before_request
    def before_request() -> None:
        debug("before_request")

    @app.before_request
    def dump_cookies() -> None:
        debug(
            dict(**session),
            g.user,
        )

    config_ = dict(sorted(app.config.items()))
    print("CONFIG:")
    debug(config_)
    print()

    print("ENV:")
    env_ = dict(sorted(os.environ.items()))
    debug(env_)


def register_blueprints(app: Flask) -> None:
    for name in find_modules(MODULES, include_packages=True):
        module = import_string(name)
        if not hasattr(module, "blueprint"):
            continue

        logger.debug("Registering blueprint: {}", module.blueprint)
        app.register_blueprint(module.blueprint)


def register_everything_else(app: Flask) -> None:
    for callback in lookup("register_on_app"):
        callback(app)


def register_perf_watcher(app: Flask) -> None:
    class Timer:
        def __init__(self) -> None:
            self.start = time.time()
            self.url = request.url

        def elapsed(self) -> float:
            return time.time() - self.start

        def info(self) -> str:
            return f"Request {self.url} took {self.elapsed():.2f}s"

    @app.before_request
    def start_timer() -> None:
        g.timer = Timer()

    @app.after_request
    def stop_timer(response: Response):
        timer = getattr(g, "timer", None)
        if timer and timer.elapsed() > MAX_REQUEST_DURATION:
            logger.debug(timer.info())
        return response


def register_filters(app: Flask) -> None:
    app.template_filter("label")(make_label)


def register_stripe(app: Flask) -> None:
    stripe.api_key = app.config.get("STRIPE_API_KEY")


def register_extra_apps(app: Flask) -> None:
    pass
    # app.register_blueprint(rq_dashboard.blueprint, url_prefix="/rq")
