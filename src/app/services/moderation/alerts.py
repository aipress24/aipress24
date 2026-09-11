# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Content alert moderation services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import make_response
from werkzeug import Response
from werkzeug.exceptions import BadRequest

from app.constants import CONTENT_ALERT_REASONS
from app.flask.extensions import db
from app.flask.lib.toaster import toast
from app.logging import warn
from app.models.content_alert import ContentAlert
from app.services.emails.mailers import ContentAlertMail

if TYPE_CHECKING:
    from app.models.auth import User


def submit_content_alert(
    user: User,
    post_id: int,
    post_title: str,
    post_type: str,
    post_url: str,
    post_author_name: str,
    form: Any,
) -> Response:
    """Record and notify a user content alert."""
    message = form.get("message", "").strip() if hasattr(form, "get") else ""
    if hasattr(form, "getlist"):
        raw_reasons = form.getlist("reasons")
    else:
        raw = form.get("reasons", []) if hasattr(form, "get") else []
        raw_reasons = raw if isinstance(raw, list) else [raw]

    if not raw_reasons and hasattr(form, "get") and form.get("reasons"):
        raw_reasons = [form.get("reasons", "").strip()]
    raw_reasons = [r for r in raw_reasons if r]

    reasons: list[str] = []
    for r in raw_reasons:
        label = CONTENT_ALERT_REASONS.get(r, r)
        if label and label not in reasons:
            reasons.append(label)

    if not reasons:
        msg = "Veuillez sélectionner au moins un motif de signalement."
        raise BadRequest(msg)

    if len(reasons) == 1:
        autre_label = CONTENT_ALERT_REASONS.get("autre")
        if reasons == [autre_label] and not message:
            msg = "Veuillez préciser le champ détails."
            raise BadRequest(msg)

    reason_label = ", ".join(reasons)

    warn(
        f"Content alert for {post_type} {post_id} {post_title!r} "
        f"by uid {user.id} {user.email!r}: reasons={reasons!r}"
    )

    reporter_name = user.full_name or user.email

    try:
        content_alert = ContentAlert(
            post_id=post_id,
            post_title=post_title,
            post_type=post_type,
            post_url=post_url,
            post_author_name=post_author_name,
            reasons=reasons,
            message=message,
            reporter_id=user.id,
            reporter_email=user.email,
            reporter_name=reporter_name,
        )
        db.session.add(content_alert)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        warn(f"Failed to record content alert in db for {post_type} {post_id}: {e}")

    try:
        alert_mail = ContentAlertMail(
            post_id=post_id,
            post_title=post_title,
            post_url=post_url,
            post_type=post_type,
            post_author_name=post_author_name,
            reason_label=reason_label,
            message=message,
            reporter_email=user.email,
            reporter_name=reporter_name,
        )
        alert_mail.send()
    except Exception as e:
        warn(f"Failed to send content alert email for {post_type} {post_id}: {e}")

    response = make_response("", 200)
    toast(response, "Signalement envoyé. Merci de votre vigilance.")
    return response
