# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Preferences home view (redirects to profile)."""

from __future__ import annotations

from werkzeug.utils import redirect

from app.flask.routing import url_for
from app.modules.preferences import blueprint


@blueprint.route("/")
def home():
    """Préférences"""
    return redirect(url_for(".profile"))
