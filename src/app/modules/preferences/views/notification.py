# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Préférences de notification — `PRF-06`.

Calqué sur « Options de contact » : mêmes gestes, même stockage JSON
sur le profil, même aller-retour formulaire.
"""

from __future__ import annotations

from flask import g, render_template, request
from flask.views import MethodView
from werkzeug.utils import redirect

from app.enums import (
    NOTIFICATION_CATEGORY_LABELS,
    OPTIONAL_NOTIFICATION_CATEGORIES,
)
from app.flask.extensions import db
from app.flask.routing import url_for
from app.modules.preferences import blueprint


class NotificationView(MethodView):
    """Notifications."""

    def get(self):
        profile = g.user.profile
        enabled = profile.all_notification_preferences()
        categories = [
            (
                category.value,
                *NOTIFICATION_CATEGORY_LABELS[category],
                enabled[category.value],
            )
            for category in OPTIONAL_NOTIFICATION_CATEGORIES
        ]
        return render_template(
            "pages/preferences/pref-notification.j2",
            title="Notifications",
            categories=categories,
        )

    def post(self):
        if request.form.get("submit") == "cancel":
            return redirect(url_for(".notification"))

        user = g.user
        user.profile.parse_form_notification_preferences(dict(request.form))
        db.session.merge(user)
        db.session.commit()
        return redirect(url_for(".notification"))


blueprint.add_url_rule(
    "/notification", view_func=NotificationView.as_view("notification")
)
