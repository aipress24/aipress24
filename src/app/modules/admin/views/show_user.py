# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin show user views."""

from __future__ import annotations

from typing import ClassVar

from arrow import now
from flask import Response, render_template, request, url_for
from flask.views import MethodView

from app.constants import LABEL_COMPTE_DESACTIVE, LOCAL_TZ
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.admin import blueprint
from app.modules.admin.utils import gc_organisation, remove_user_organisation
from app.modules.kyc.views import admin_info_context


class ShowUserView(MethodView):
    """Show user detail page with actions."""

    decorators: ClassVar[list] = [
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
                db.session.commit()
                response = Response("")
                response.headers["HX-Redirect"] = url_for("admin.users")
            case "remove_org":
                self._remove_organisation(user)
                db.session.commit()
                response = Response("")
                response.headers["HX-Redirect"] = url_for("admin.show_user", uid=uid)
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = url_for("admin.users")

        return response

    def _deactivate_profile(self, user: User) -> None:
        """Deactivate user profile.

        Note: Does NOT commit - caller is responsible for committing.
        """
        user.active = False
        user.validation_status = LABEL_COMPTE_DESACTIVE
        user.validated_at = now(LOCAL_TZ)
        db.session.merge(user)

    def _remove_organisation(self, user: User) -> None:
        """Remove user from organisation.

        Note: Does NOT commit - caller is responsible for committing.
        """
        previous_organisation = user.organisation
        remove_user_organisation(user)
        gc_organisation(previous_organisation)


# Register the view
blueprint.add_url_rule("/show_user/<uid>", view_func=ShowUserView.as_view("show_user"))
