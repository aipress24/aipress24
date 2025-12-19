# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Other preferences pages (redirects and placeholders)."""

from __future__ import annotations

from flask import render_template
from werkzeug.utils import redirect

from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.preferences import blueprint


@blueprint.route("/password")
@nav(menu=False)  # Not in regular menu, uses redirect
def password():
    """Mot de passe"""
    return redirect(url_for("security.change_password"))


@blueprint.route("/email")
@nav(menu=False)  # Not in regular menu, uses redirect
def email():
    """Adresse email"""
    return redirect(url_for("security.change_email"))


@blueprint.route("/security")
@nav(menu=False)  # Placeholder
def security():
    """Sécurité"""
    ctx = {"title": "Sécurité"}
    return render_template("pages/preferences/placeholder.j2", **ctx)


@blueprint.route("/notification")
@nav(menu=False)  # Placeholder
def notification():
    """Notification"""
    ctx = {"title": "Notification"}
    return render_template("pages/preferences/placeholder.j2", **ctx)


@blueprint.route("/integration")
@nav(menu=False)  # Placeholder
def integration():
    """Intégration"""
    ctx = {"title": "Intégration"}
    return render_template("pages/preferences/placeholder.j2", **ctx)
