# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin show user views."""

from __future__ import annotations

from arrow import now
from flask import Response, render_template, request, url_for
from flask.views import MethodView

from app.constants import LABEL_COMPTE_DESACTIVE, LOCAL_TZ
from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.admin import blueprint
from app.modules.admin.utils import gc_organisation, remove_user_organisation
from app.modules.kyc.views import admin_info_context
from app.services.roles import add_role


class ShowUserView(MethodView):
    """Show user detail page with actions."""

    decorators = [
        nav(parent="users", icon="clipboard-document-check", label="Détail utilisateur")
    ]

    def get(self, uid: str):
        user = get_obj(uid, User)
        context = admin_info_context(user)
        context.update(
            {
                "user": user,
                "org": user.organisation,
                "title": "Informations sur l'utilisateur",
            }
        )
        return render_template("admin/pages/show_user.j2", **context)

    def post(self, uid: str):
        user = get_obj(uid, User)
        action = request.form.get("action", "")

        match action:
            case "deactivate":
                self._deactivate_profile(user)
                response = Response("")
                response.headers["HX-Redirect"] = url_for("admin.users")
            case "remove_org":
                self._remove_organisation(user)
                response = Response("")
                response.headers["HX-Redirect"] = url_for("admin.show_user", uid=uid)
            case "toggle-manager":
                self._toggle_manager(user)
                response = Response("")
            case "toggle-leader":
                self._toggle_leader(user)
                response = Response("")
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = url_for("admin.users")

        return response

    def _deactivate_profile(self, user: User) -> None:
        """Deactivate user profile."""
        user.active = False
        user.validation_status = LABEL_COMPTE_DESACTIVE
        user.validated_at = now(LOCAL_TZ)
        db.session.merge(user)
        db.session.commit()

    def _remove_organisation(self, user: User) -> None:
        """Remove user from organisation."""
        previous_organisation = user.organisation
        remove_user_organisation(user)
        gc_organisation(previous_organisation)
        db.session.commit()

    def _toggle_manager(self, user: User) -> None:
        """Toggle manager role for user."""
        if not user.organisation or user.organisation.is_auto:
            return
        if user.is_manager:
            user.remove_role(RoleEnum.MANAGER)
        else:
            add_role(user, RoleEnum.MANAGER)
        db.session.merge(user)
        db.session.commit()

    def _toggle_leader(self, user: User) -> None:
        """Toggle leader role for user."""
        if not user.organisation or user.organisation.is_auto:
            return
        if user.is_leader:
            user.remove_role(RoleEnum.LEADER)
        else:
            add_role(user, RoleEnum.LEADER)
        db.session.merge(user)
        db.session.commit()


# Register the view
blueprint.add_url_rule(
    "/show_user/<uid>", view_func=ShowUserView.as_view("show_user")
)
