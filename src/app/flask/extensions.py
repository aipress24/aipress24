"""Flask extensions setup and initialization."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys

import fsspec
from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types.file_object import storages
from advanced_alchemy.types.file_object.backends.fsspec import FSSpecBackend
from flask import Flask
from flask_babel import Babel
from flask_htmx import HTMX
from flask_mailman import Mail
from flask_migrate import Migrate
from flask_security import Security, SQLAlchemySessionUserDatastore
from flask_sqlalchemy import SQLAlchemy
from flask_talisman import DEFAULT_CSP_POLICY, Talisman
from flask_vite import Vite
from loguru import logger
from pagebar.flask import Pagebar
from pytz import timezone

from app.models.auth import Role, User
from app.models.base import Base

# Tell UUIDAuditBase to use the same metadata as Base
# to fix ForeignKey references work across models using different bases
UUIDAuditBase.metadata = Base.metadata

PARIS_TZ = timezone("Europe/Paris")


def import_all_models():
    """Import all model modules to register tables."""
    import app.models.admin
    import app.models.auth
    import app.models.base
    import app.models.base_content
    import app.models.content
    import app.models.email_log
    import app.models.geoloc
    import app.models.invitation
    import app.models.jobs
    import app.models.lifecycle
    import app.models.meta
    import app.models.organisation
    import app.models.web
    import app.modules.biz.models
    import app.modules.bw.bw_activation.models
    import app.modules.events.models
    import app.modules.swork.models
    import app.modules.wip.models
    import app.modules.wire.models
    import app.services.zip_codes._models

    # These modules are imported for side effect
    assert app.modules.biz.models
    assert app.modules.bw.bw_activation.models
    assert app.modules.events.models
    assert app.modules.swork.models
    assert app.modules.wip.models
    assert app.modules.wire.models
    assert app.models.admin
    assert app.models.auth
    assert app.models.base
    assert app.models.base_content
    assert app.models.content
    assert app.models.email_log
    assert app.models.geoloc
    assert app.models.invitation
    assert app.models.jobs
    assert app.models.lifecycle
    assert app.models.meta
    assert app.models.organisation
    assert app.models.web
    assert app.services.zip_codes._models


# Create all extensions as global variables
db = SQLAlchemy(
    model_class=Base,
    # metadata=UUIDAuditBase.metadata,
)
migrate = Migrate()

# Alternative to Flask-SQLAlchemy. Not sure if it's better.
# db = Alchemical(model_class=Base)

mail = Mail()
vite = Vite()
babel = Babel(default_locale="fr", default_timezone=PARIS_TZ)
# wakaq = WakaQ()
# session = Session()

security = Security()

htmx = HTMX()


def register_extensions(app: Flask) -> None:
    """Register all Flask extensions.

    Args:
        app: Flask application instance.
    """
    logger.debug("Registering all extensions")

    import_all_models()
    # UUIDAuditBase.metadata is now set to Base.metadata (see UUIDAuditBase.metadata = Base.metadata)
    # All models should now share the same metadata

    db.init_app(app)
    # register_local_storage(app)
    register_s3_storage(app)

    mail.init_app(app)
    babel.init_app(app)
    # migrate = Migrate(app, db)
    migrate.init_app(app, db)
    vite.init_app(app)
    # rq.init_app(app)
    # wakaq.init_app(app)
    setup_security(app, db)
    htmx.init_app(app)
    Pagebar(app, package="aipress24-flask", unsafe=app.debug)

    if app.debug:
        setup_debug_toolbar(app)

    if not app.debug and not app.testing:
        csp = app.config.get("CONTENT_SECURITY_POLICY", DEFAULT_CSP_POLICY)
        Talisman(app, content_security_policy=csp, force_https=False)


def register_s3_storage(app: Flask) -> None:
    endpoint_url = app.config["S3_ENDPOINT_URL"]
    access_key = app.config["S3_ACCESS_KEY_ID"]
    secret_key = app.config["S3_SECRET_ACCESS_KEY"]
    bucket_name = app.config["S3_BUCKET_NAME"]
    use_ssl = app.config.get("S3_USE_SSL", False)

    s3_fs = fsspec.filesystem(
        "s3",
        client_kwargs={
            "endpoint_url": endpoint_url,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "verify": use_ssl,
        },
        use_ssl=use_ssl,
    )
    prefix = f"{bucket_name}/files"
    storages.register_backend(FSSpecBackend(fs=s3_fs, key="s3", prefix=prefix))


def register_local_storage(app: Flask) -> None:
    # Path(app.config["STORAGE_ROOT"]).mkdir(parents=True, exist_ok=True)
    local_fs = fsspec.filesystem("file")
    storages.register_backend(
        FSSpecBackend(fs=local_fs, key="local", prefix=app.config["STORAGE_ROOT"])
    )


def setup_debug_toolbar(app: Flask) -> None:
    """Setup Flask debug toolbar for development.

    `flask_debugtoolbar` is a dev-only dependency: if it's missing (e.g.
    a prod image accidentally booted with `FLASK_DEBUG=1`) the toolbar
    is silently skipped rather than crashing app startup.
    """
    try:
        from flask_debugtoolbar import DebugToolbarExtension
    except ImportError:
        return

    DebugToolbarExtension(app)


def setup_security(app: Flask, db: SQLAlchemy) -> None:
    """Setup Flask-Security."""

    user_datastore = SQLAlchemySessionUserDatastore(db.session, User, Role)
    security.init_app(app, user_datastore)
    _patch_flask_security_cache_control(app)
    _install_password_bypass(app)


def _install_password_bypass(app: Flask) -> None:
    """Make every password check succeed, when `ACCEPT_ANY_PASSWORD` is set.

    For end-to-end runs against a restored database whose password
    hashes do not match the test fixtures. `UNSECURE` is required as
    well, so a single variable cannot open every account; setting the
    flag alone stops the app from starting rather than being ignored.

    Patching `User` here rather than defining the behaviour on the model
    keeps `app.models` free of Flask (`tests/a_unit/test_archi.py`), and
    means that with the flag off the login path is exactly the code it
    was before — no config lookup on every password check.
    """
    if not app.config.get("ACCEPT_ANY_PASSWORD"):
        return
    if not app.config.get("UNSECURE"):
        msg = (
            "ACCEPT_ANY_PASSWORD is set but UNSECURE is not. This flag "
            "accepts any password for any account and must never be set "
            "on its own; it is refused here rather than silently ignored."
        )
        raise RuntimeError(msg)

    def accept_any_password(self: User, password: str | bytes) -> bool:
        logger.warning("ACCEPT_ANY_PASSWORD: accepting any password for {}", self.email)
        return True

    User.verify_and_update_password = accept_any_password

    banner = (
        "ACCEPT_ANY_PASSWORD is ON: every password is accepted for every "
        "account. Never run this against production data you care about."
    )
    logger.warning(banner)
    # Straight to stderr as well: loguru emits nothing under `flask run`
    # in this app, and a switch that opens every account must not be
    # announced only through a channel that can be silenced.
    print(f"\n*** {banner} ***\n", file=sys.stderr, flush=True)


def _patch_flask_security_cache_control(app: Flask) -> None:
    """Replace Flask-Security's `add_cache_control` hook with a clean one.

    Upstream iterates the CACHE_CONTROL config dict and writes each key
    via `resp.cache_control[attr] = value`, which is dict-style access
    on Werkzeug's CacheControl proxy. Standalone directives (`private`,
    `no-store`, ...) then serialise as `private=True`, which is invalid
    per RFC 7234 — browsers fall back to treating it as the bare token,
    but the header on the wire is malformed on every authenticated
    response. Our replacement uses attribute setters, which Werkzeug
    knows to serialise as bare tokens. Preserves the original's
    registration slot so handler ordering is unchanged; no-ops if the
    upstream hook can't be found (future Flask-Security rewrite).
    """
    from flask_security.utils import config_value

    def clean_add_cache_control(resp):
        cc = config_value("CACHE_CONTROL", app=app) or {}
        for attr, value in cc.items():
            setattr(resp.cache_control, attr.replace("-", "_"), value)
        return resp

    hooks = app.after_request_funcs.get(None, [])
    for i, hook in enumerate(hooks):
        hook_name = getattr(hook, "__name__", "")
        hook_module = getattr(hook, "__module__", "")
        if hook_name == "add_cache_control" and hook_module.startswith(
            "flask_security"
        ):
            hooks[i] = clean_add_cache_control
            return
