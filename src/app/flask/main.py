"""Main Flask application factory and configuration."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import os
import time

import stripe
import svcs
from flask import Flask, Response, g, request, session
from flask_super import register_commands
from flask_super.registry import lookup
from flask_super.scanner import scan_packages
from loguru import logger
from sqlalchemy.orm import scoped_session
from svcs.flask import container
from werkzeug.utils import find_modules, import_string

from app.blueprints.ontology import ontology_bp
from app.flask import services
from app.flask.cli.bootstrap import bootstrap
from app.flask.config import setup_config
from app.flask.extensions import db, register_extensions
from app.flask.hooks import register_hooks
from app.flask.jinja import register_context_processors
from app.flask.lib.macros import register_macros
from app.flask.lib.nav import register_nav
from app.flask.lib.pages import register_pages
from app.flask.lib.pywire import (
    register_components,
    register_pywire,
    register_wired_components,
)
from app.flask.util import utcnow
from app.lib import debugging
from app.lib.debugging import debug
from app.logging import configure_logging
from app.services.stripe.utils import (
    check_stripe_public_key,
    check_stripe_secret_key,
    check_stripe_webhook_secret,
)
from app.ui.datetime_filter import make_localdt, make_naivedt
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
configure_logging()


def create_app(config=None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config: Optional configuration object for testing.

    Returns:
        Flask: Configured Flask application instance.
    """
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app = svcs.flask.init_app(app)

    # 1: set up app.config properly
    setup_config(app, config)
    # force flask-security to use non naive datetime
    app.config["SECURITY_DATETIME_FACTORY"] = utcnow

    # 2: Scan to pre-register callbacks, services, etc.
    scan_packages(SCAN_PACKAGES)

    # 3. Perform registrations on app
    register_all(app)

    return app


def register_all(app: Flask) -> None:
    """Register all application components, extensions, and services.

    Args:
        app: Flask application instance.
    """
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

    # Register new navigation system (after blueprints)
    register_nav(app)
    register_extra_apps(app)
    register_pywire(app)
    register_everything_else(app)

    # Not used (yet?)
    # register_oauth_providers(app)

    # Local imports bc import cycles
    from app.dramatiq.setup import init_dramatiq

    init_dramatiq(app)

    # Check completeness of Stripe configuration
    _check_stripe_configuration(app)


def _check_stripe_configuration(app: Flask) -> None:
    """Check completeness of Stripe configuration.

    Args:
        app: Flask application instance.
    """
    if not check_stripe_secret_key(app):
        logger.warning("STRIPE_SECRET_KEY not found in config")
    if not check_stripe_public_key(app):
        logger.warning("STRIPE_PUBLIC_KEY not found in config")
    if not check_stripe_webhook_secret(app):
        logger.warning("STRIPE_WEBHOOK_SECRET not found in config")


def register_debug_hooks(app: Flask) -> None:
    """Register debug hooks for development.

    Args:
        app: Flask application instance.
    """
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
    """Register all module blueprints.

    Args:
        app: Flask application instance.
    """
    for name in find_modules(MODULES, include_packages=True):
        module = import_string(name)
        if not hasattr(module, "blueprint"):
            continue

        logger.debug("Registering blueprint: {}", module.blueprint)
        app.register_blueprint(module.blueprint)

    # Manual blueprint registrations (if any)
    app.register_blueprint(ontology_bp, url_prefix="/admin/ontology")


def register_everything_else(app: Flask) -> None:
    """Register remaining components via callbacks.

    Args:
        app: Flask application instance.
    """
    for callback in lookup("register_on_app"):
        callback(app)


def register_perf_watcher(app: Flask) -> None:
    """Register performance monitoring hooks.

    Args:
        app: Flask application instance.
    """

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
    """Register Jinja2 template filters.

    Args:
        app: Flask application instance.
    """
    app.template_filter("label")(make_label)
    app.template_filter("localdt")(make_localdt)
    app.template_filter("naivedt")(make_naivedt)


def register_stripe(app: Flask) -> None:
    """Configure Stripe API key.

    Args:
        app: Flask application instance.
    """
    stripe.api_key = app.config.get("STRIPE_API_KEY")


def register_extra_apps(app: Flask) -> None:
    """Register additional applications.

    Args:
        app: Flask application instance.
    """
    # app.register_blueprint(rq_dashboard.blueprint, url_prefix="/rq")


def bootstrap_db(app) -> None:
    """Bootstrap the database with initial data.

    Args:
        app: Flask application instance.
    """
    with app.app_context():
        session = container.get(scoped_session)
        try:
            country_count: int = session.execute(
                "SELECT COUNT(*) FROM zip_country"
            ).scalar()
        except Exception:
            country_count = 0
            db.create_all()

    if country_count == 0:
        bootstrap()
