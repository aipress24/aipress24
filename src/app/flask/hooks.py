# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib.metadata
from collections.abc import Callable
from typing import cast

from flask import (
    Flask,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_security.core import AnonymousUser
from flask_security.signals import user_authenticated
from svcs.flask import container
from werkzeug import Response
from werkzeug.exceptions import (
    Forbidden,
    HTTPException,
    InternalServerError,
    NotFound,
    Unauthorized,
)

from app.flask.doorman import doorman
from app.flask.lib.proxies import unproxy
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.lib.debugging import debug
from app.models.auth import User
from app.services.menus import MenuService
from app.services.notifications import NotificationService
from app.services.promotions import PromotionService
from app.settings import get_settings

TIMEOUT = 5

# Session keys whose prefix indicates per-module UI state (search
# filters, active tab, sort, etc). Cleared at every login so a
# user never inherits the previous occupant's view of a list.
# Ref: bug #0118 — events filter persisted across users.
_PER_USER_SESSION_KEY_PREFIXES: tuple[str, ...] = (
    "events:",
    "wire:",
    "swork:",
    "biz:",
)


def register_hooks(app: Flask) -> None:
    app.before_request(inject_extensions)
    app.before_request(authenticate_user)
    app.before_request(doorman.check_access)
    app.context_processor(inject_extra_context)
    app.errorhandler(Unauthorized)(handle_authentication_error)
    app.errorhandler(Forbidden)(handle_forbidden_error)
    app.errorhandler(NotFound)(handle_not_found_error)
    app.errorhandler(InternalServerError)(handle_internal_error)
    user_authenticated.connect(_clear_per_user_session_state, app)

    # app.after_request(dump_session)
    # template_rendered.connect_via(app)(log_template_info)


def _clear_per_user_session_state(_sender, **_kwargs) -> None:
    """Drop all `<module>:<key>` session entries on login.

    Flask-Security keeps the same browser session cookie when one
    user logs out and another logs in (only the auth identifiers
    are rotated). Without this hook, UI state stored under module
    prefixes (e.g. `events:state`, `wire:tab`) would leak between
    users sharing a browser.
    """
    for key in list(session.keys()):
        if key.startswith(_PER_USER_SESSION_KEY_PREFIXES):
            session.pop(key, None)


def inject_extensions() -> None:
    g.extensions = current_app.extensions


def handle_authentication_error(_e):
    # Ticket #0227: preserve the destination so a protected deep link hit
    # while logged out (e.g. a « consultation offerte » article reached
    # from the gift email) returns the user there after login, instead of
    # dumping them on the default landing page (the « parcours du
    # combattant » : se reconnecter, rouvrir un onglet, recoller l'URL).
    return redirect(url_for("security.login", next=request.path))


def _delegate_to_api(e: HTTPException) -> ResponseReturnValue | None:
    """Rendre la main au module API, ou `None` si ce n'est pas son ressort.

    `/api/v1` a son propre rendu JSON, et un client qui reçoit du HTML à
    la place d'un corps d'erreur ne sait rien en faire. Mais un
    gestionnaire enregistré pour `NotFound` est plus spécifique que
    celui de l'API, enregistré pour `HTTPException` : sans cette
    délégation, les 404 de l'API repartaient en HTML.

    Le gestionnaire est **cherché dans le registre de l'application**,
    pas importé : `setup.cfg` fait de `app.modules.api_v1` une feuille
    que `app.flask` n'a pas le droit d'importer (contrat « The public
    API module is a leaf »).
    """
    if not request.path.startswith("/api/"):
        return None
    registered = (
        current_app.error_handler_spec.get(None, {}).get(None, {}).get(HTTPException)
    )
    if registered is None:
        return e.get_response()
    # Flask type ses gestionnaires comme pouvant être asynchrones ; cette
    # application n'en a aucun. Le `cast` énonce ce fait, plutôt que de
    # faire taire un code de diagnostic entier.
    handler = cast("Callable[[HTTPException], ResponseReturnValue]", registered)
    return handler(e)


def handle_not_found_error(e: NotFound) -> ResponseReturnValue:
    """Rendre une page 404 lisible plutôt que celle de Werkzeug.

    Il n'y avait aucun gestionnaire pour `NotFound` : un contenu retiré
    servait la page par défaut — en anglais, sans issue, et affichant le
    message interne de l'exception (« Can't match id 750100636… »). Un
    membre y arrivait depuis une notification de la cloche pointant une
    publication depuis dépubliée.

    `e.description` n'est **pas** repris : il est écrit pour les logs,
    pas pour un lecteur, et nomme des identifiants internes.

    Les chemins d'API gardent leur rendu JSON, comme le fait déjà
    `handle_forbidden_error` pour le 403.
    """
    api_response = _delegate_to_api(e)
    if api_response is not None:
        return api_response
    return render_template("errors/404.j2"), 404


def handle_internal_error(e: InternalServerError) -> ResponseReturnValue:
    """Même règle pour la 500 : jamais de page nue.

    Le gabarit est autonome — il n'hérite pas de `layout.html`, dont le
    rendu peut être ce qui vient d'échouer.
    """
    api_response = _delegate_to_api(e)
    if api_response is not None:
        return api_response
    return render_template("errors/500.j2"), 500


def handle_forbidden_error(e: Forbidden) -> Response:
    """Handle 403 Forbidden redirecting to root '/' for UI pages.

    Also flash a notification.

    API endpoints (/api/) return the standard 403 Forbidden error response.
    """
    if request.path.startswith("/api/"):
        return e.get_response()

    flash("Accès non autorisé.", "warning")
    resp = redirect("/")
    resp.headers["X-Access-Denied"] = "true"
    return resp


def authenticate_user() -> None:
    if request.path.startswith("/static"):
        return

    if current_user.is_authenticated:
        g.user = unproxy(current_user)
        return

    # In test mode, try to use a default test user (ID 0) if it exists
    # This is a fallback for tests that don't explicitly authenticate
    if current_app.testing:
        try:
            g.user = get_obj(0, User)
            return
        except NotFound:
            # If user 0 doesn't exist, continue to anonymous user
            pass

    g.user = AnonymousUser()
    return


def inject_extra_context():
    menu_service = container.get(MenuService)
    notification_service = container.get(NotificationService)
    promotion_service = container.get(PromotionService)

    try:
        version = importlib.metadata.version("aipress24-flask")
    except importlib.metadata.PackageNotFoundError:
        version = "???"

    def get_notifications() -> list:
        return notification_service.get_notifications(g.user)

    def get_unread_notification_count() -> int:
        if not getattr(g, "user", None) or g.user.is_anonymous:
            return 0
        return notification_service.get_unread_count(g.user)

    return {
        "get_promotion": promotion_service.get_promotion,
        "url_for": url_for,
        "json_data": {},
        "app_version": version,
        "menus": menu_service,
        "get_notifications": get_notifications,
        "get_unread_notification_count": get_unread_notification_count,
        "settings": get_settings(),
    }


#
# Debugging
#
def dump_session(response):
    # debug(sorted(session.items()))
    return response


def log_template_info(_sender, **kwargs) -> None:
    template = kwargs["template"]
    context = kwargs["context"]
    debug(template.name, list(context.keys()))
