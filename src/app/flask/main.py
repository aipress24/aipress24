"""Main Flask application factory and configuration."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
#
# ruff: noqa: E402  # warnings filter must be set before other imports

from __future__ import annotations

import warnings

# Suppress deprecation warning from passlib using pkg_resources
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import importlib
import os
import pkgutil
import time
from collections.abc import Iterable

import stripe
import svcs
from flask import Flask, Response, g, request, session
from flask_super import register_commands
from flask_super.registry import lookup
from loguru import logger
from sqlalchemy.orm import scoped_session
from svcs.flask import container
from werkzeug.utils import find_modules, import_string

from app.blueprints.ontology import ontology_bp
from app.flask import services
from app.flask.cli.bootstrap import bootstrap
from app.flask.cli.roles import register_roles_commands, register_users_commands
from app.flask.config import setup_config
from app.flask.extensions import db, register_extensions
from app.flask.hooks import register_hooks
from app.flask.jinja import register_context_processors
from app.flask.lib.macros import register_macros
from app.flask.lib.nav import register_nav
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
from app.settings.constants import MAX_CONTENT_LENGTH
from app.ui.datetime_filter import make_localdt, make_naivedt
from app.ui.labels import make_label

# Where we're looking for blueprints
MODULES = "app.modules"

# All modules and packages that should be scanned for side effects
# (e.g. registering callbacks, service, etc.)
SCAN_PACKAGES = [
    "app",
]

# Sub-packages excluded from the scan. `app.faker` depends on `faker` +
# `mimesis` (dev-only deps) and is only ever used by the `flask fake` CLI;
# it must not be imported during normal app startup.
SCAN_EXCLUDES: frozenset[str] = frozenset({"app.faker"})


def _scan_packages_filtered(packages: Iterable[str]) -> None:
    """Scan packages for side effects, skipping `SCAN_EXCLUDES` subtrees."""
    for package_name in packages:
        if _is_excluded(package_name):
            continue
        root = importlib.import_module(package_name)
        if not hasattr(root, "__path__"):
            continue
        prefix = root.__name__ + "."
        for _, module_name, _ in pkgutil.walk_packages(root.__path__, prefix):
            if _is_excluded(module_name):
                continue
            importlib.import_module(module_name)


def _is_excluded(module_name: str) -> bool:
    for excluded in SCAN_EXCLUDES:
        if module_name == excluded or module_name.startswith(excluded + "."):
            return True
    return False


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
    app = svcs.flask.init_app(app)  # type: ignore[attr-defined]

    # 1: set up app.config properly
    setup_config(app, config)
    # force flask-security to use non naive datetime
    app.config["SECURITY_DATETIME_FACTORY"] = utcnow
    # Flask-Security's default is {"private": True, "no-store": True},
    # applied globally via an after_app_request hook. `no-store` kills
    # caching on every response (including /media immutable assets) and
    # buys little — session cookies are already HttpOnly + SameSite.
    # `private` alone still prevents shared proxies from caching.
    app.config["SECURITY_CACHE_CONTROL"] = {"private": True}
    # Without this, Flask-Security's change-email confirmation falls back
    # to url_for_security("change_email") — i.e. the "request a change"
    # form — instead of landing the user somewhere useful. Redirect to
    # preferences (where the action originated). ref: bug #0088.
    app.config["SECURITY_POST_CHANGE_EMAIL_VIEW"] = "/preferences/"
    # Cap on incoming request body size — defence in depth alongside
    # nginx's `client_max_body_size`. Werkzeug rejects oversize uploads
    # before the view sees them.
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

    # 2: Scan to pre-register callbacks, services, etc.
    _scan_packages_filtered(SCAN_PACKAGES)

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
    register_coverage(app)
    register_stripe(app)

    # Register CLI commands
    register_commands(app)
    register_roles_commands(app)
    register_users_commands(app)

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

    # Register blueprints
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

        # Call register_views() if available to defer view imports
        # This helps avoid circular imports during module loading
        if hasattr(module, "register_views"):
            module.register_views()

        logger.debug("Registering blueprint: {}", module.blueprint)
        app.register_blueprint(module.blueprint)

    # Manual blueprint registrations (if any)
    app.register_blueprint(ontology_bp, url_prefix="/admin/ontology")

    # Register the BW activation module blueprint
    from app.modules.bw import bw_activation_bp

    app.register_blueprint(bw_activation_bp, url_prefix="/BW")


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


def register_coverage(app: Flask) -> None:
    """Mount /debug/coverage in dev/CI for live coverage of e2e runs.

    Fail-closed by design — only registers if the app is in debug mode
    or ``FLASK_COVERAGE_PASSWORD`` is set. The package itself is a dev
    dep, so on prod (no debug, no password, package likely missing)
    this is a no-op.
    """
    if not (app.debug or os.environ.get("FLASK_COVERAGE_PASSWORD")):
        return
    try:
        from flask_coverage import FlaskCoverage
    except ImportError:
        return
    FlaskCoverage(app)


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
            from sqlalchemy import text

            country_count: int = (
                session.execute(text("SELECT COUNT(*) FROM zip_country")).scalar() or 0
            )
        except Exception:
            country_count = 0
            db.create_all()

    if country_count == 0:
        bootstrap()
