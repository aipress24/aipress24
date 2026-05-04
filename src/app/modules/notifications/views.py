# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast
from urllib.parse import urlparse

from flask import g, redirect, request
from svcs.flask import container
from werkzeug import Response

from app.flask.extensions import db
from app.models.auth import User
from app.services.notifications import NotificationService

from . import blueprint


def _is_safe_url(target: str) -> bool:
    """True iff `target` is same-origin (or relative)."""
    parsed = urlparse(target)
    return not parsed.netloc or parsed.netloc == request.host


def _safe_next_url(fallback: str = "/", form_key: str = "next") -> str:
    """Return the form-`form_key` URL if it's local, otherwise fallback.

    Prevents open-redirect from a crafted `next` / `url` / Referer.
    """
    target = request.form.get(form_key) or request.referrer or fallback
    if not _is_safe_url(target):
        return fallback
    return target or fallback


@blueprint.route("/mark-all-read", methods=["POST"])
def mark_all_read() -> Response:
    user = cast(User, g.user)
    service = container.get(NotificationService)
    service.mark_all_as_read(user)
    db.session.commit()
    return redirect(_safe_next_url())


@blueprint.route("/<int:notification_id>/read", methods=["POST"])
def mark_read(notification_id: int) -> Response:
    """Mark one notification as read and follow its target URL if any.

    Used by the bell dropdown: clicking a notification flags it read
    and navigates to the content it points to. The `url` form param
    is sanitised against open-redirect — same-origin only.
    """
    user = cast(User, g.user)
    service = container.get(NotificationService)
    service.mark_as_read(notification_id, user)
    db.session.commit()

    return redirect(_safe_next_url(form_key="url"))
