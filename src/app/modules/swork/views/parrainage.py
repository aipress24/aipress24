# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Parrainage view."""

from __future__ import annotations

import re
from typing import ClassVar, cast

import arrow
from email_validator import EmailNotValidError, validate_email
from flask import flash, redirect, render_template, request
from flask.views import MethodView
from flask_login import current_user

from app.constants import (
    LOCAL_TZ,
    PARRAINAGE_MAX_EMAILS_PER_WEEK,
    PARRAINAGE_PERIOD_DAYS,
)
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.models.auth import User
from app.models.parrainage_email_log import ParrainageEmailLog
from app.modules.swork import blueprint
from app.services.emails import ParrainageMail

MAX_INVITATIONS = PARRAINAGE_MAX_EMAILS_PER_WEEK


def parse_and_validate_emails(raw_input: str) -> tuple[list[str], list[str]]:
    """Parse and validate email addresses from raw text.

    Returns (valid_emails, invalid_emails) deduplicated while preserving order.
    """
    tokens = [t.strip() for t in re.split(r"[\s,;]+", raw_input) if t.strip()]

    valid_emails: list[str] = []
    invalid_emails: list[str] = []
    seen: set[str] = set()

    for token in tokens:
        try:
            email_info = validate_email(token, check_deliverability=False)
            normalized = email_info.normalized.lower()
            if normalized not in seen:
                seen.add(normalized)
                valid_emails.append(normalized)
        except EmailNotValidError:
            if token.lower() not in seen:
                seen.add(token.lower())
                invalid_emails.append(token)

    return valid_emails, invalid_emails


def get_user_parrainage_sent_count(
    user_id: int, period_days: int = PARRAINAGE_PERIOD_DAYS
) -> int:
    """Return count of parrainage emails sent by user in the given period."""
    now = arrow.now(LOCAL_TZ)
    period_start = now.shift(days=-period_days)
    return (
        db.session.query(ParrainageEmailLog)
        .filter(
            ParrainageEmailLog.user_id == user_id,
            ParrainageEmailLog.sent_at >= period_start,
        )
        .count()
    )


def record_parrainage_emails(user_id: int, recipient_emails: list[str]) -> None:
    """Record sent parrainage emails in ParrainageEmailLog."""
    now = arrow.now(LOCAL_TZ)
    for email in recipient_emails:
        log_entry = ParrainageEmailLog(
            user_id=user_id,
            recipient_email=email.strip().lower(),
            sent_at=now,
        )
        db.session.add(log_entry)
    db.session.commit()


def send_parrainage_emails(sender: User, recipient_emails: list[str]) -> None:
    """Send parrainage invitation emails to recipient emails."""
    sender_mail = sender.email or ""
    sender_full_name = (sender.full_name or "").strip() or sender_mail

    for email in recipient_emails:
        mail = ParrainageMail(
            sender="contact@aipress24.com",
            recipient=email,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
        )
        mail.send()


class ParrainageView(MethodView):
    """Parrainage.

    Page allowing members to invite friends to AiPRESS24.
    """

    decorators: ClassVar[list] = [nav(parent="swork", icon="heart")]

    def get(self):
        user = cast("User", current_user)
        user_id = user.id if hasattr(user, "id") and user.is_authenticated else None
        sent_count = get_user_parrainage_sent_count(user_id) if user_id else 0
        remaining = max(0, MAX_INVITATIONS - sent_count)

        return render_template(
            "pages/parrainage.j2",
            title="Parrainage",
            emails="",
            errors=[],
            success=None,
            sent_count=sent_count,
            remaining=remaining,
            max_invitations=MAX_INVITATIONS,
        )

    def post(self):
        user = cast("User", current_user)
        user_id = user.id if hasattr(user, "id") and user.is_authenticated else None

        raw_emails = request.form.get("emails", "").strip()
        sent_count = get_user_parrainage_sent_count(user_id) if user_id else 0
        remaining = max(0, MAX_INVITATIONS - sent_count)

        if not raw_emails:
            error_msg = "Veuillez saisir au moins une adresse email."
            flash(error_msg, "error")
            return (
                render_template(
                    "pages/parrainage.j2",
                    title="Parrainage",
                    emails=raw_emails,
                    errors=[error_msg],
                    success=None,
                    sent_count=sent_count,
                    remaining=remaining,
                    max_invitations=MAX_INVITATIONS,
                ),
                400,
            )

        valid_emails, invalid_emails = parse_and_validate_emails(raw_emails)

        errors: list[str] = []
        if invalid_emails:
            inv_str = ", ".join(invalid_emails)
            errors.append(f"Adresse(s) email invalide(s) : {inv_str}")

        if remaining == 0:
            errors.append(
                f"Vous avez atteint la limite de {MAX_INVITATIONS} par semaine au maximum. "
                f"Vous avez déjà envoyé {sent_count} invitation(s) au cours des {PARRAINAGE_PERIOD_DAYS} derniers jours."
            )
        elif len(valid_emails) > remaining:
            errors.append(
                f"Vous avez saisi {len(valid_emails)} adresses, mais il ne vous reste que {remaining} invitation(s) "
                f"disponible(s) sur votre quota de {MAX_INVITATIONS} par semaine au maximum "
                f"(vous en avez déjà envoyé {sent_count} cette semaine)."
            )

        if errors:
            for err in errors:
                flash(err, "error")
            return (
                render_template(
                    "pages/parrainage.j2",
                    title="Parrainage",
                    emails=raw_emails,
                    errors=errors,
                    success=None,
                    sent_count=sent_count,
                    remaining=remaining,
                    max_invitations=MAX_INVITATIONS,
                ),
                400,
            )

        if user_id:
            record_parrainage_emails(user_id, valid_emails)

        send_parrainage_emails(user, valid_emails)

        count = len(valid_emails)
        flash(
            f"Vos invitations ont été prises en compte pour {count} contact(s).",
            "success",
        )
        return redirect(url_for("swork.parrainage"))


parrainage_view = ParrainageView.as_view("parrainage")

blueprint.add_url_rule(
    "/parrainage/",
    view_func=parrainage_view,
    methods=["GET", "POST"],
)
blueprint.add_url_rule(
    "/parrainages/",
    view_func=parrainage_view,
    methods=["GET", "POST"],
)
