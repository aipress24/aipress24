# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Parrainage view."""

from __future__ import annotations

import re
from typing import ClassVar

from email_validator import EmailNotValidError, validate_email
from flask import flash, redirect, render_template, request
from flask.views import MethodView

from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.swork import blueprint

MAX_INVITATIONS = 50


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


class ParrainageView(MethodView):
    """Parrainage.

    Page allowing members to invite friends to AiPRESS24.
    """

    decorators: ClassVar[list] = [nav(parent="swork", icon="heart")]

    def get(self):
        return render_template(
            "pages/parrainage.j2",
            title="Parrainage",
            emails="",
            errors=[],
            success=None,
        )

    def post(self):
        raw_emails = request.form.get("emails", "").strip()

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
                ),
                400,
            )

        valid_emails, invalid_emails = parse_and_validate_emails(raw_emails)

        errors: list[str] = []
        if invalid_emails:
            inv_str = ", ".join(invalid_emails)
            errors.append(f"Adresse(s) email invalide(s) : {inv_str}")

        if len(valid_emails) > MAX_INVITATIONS:
            errors.append(
                f"Vous ne pouvez inviter que {MAX_INVITATIONS} par semaine au maximum."
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
                ),
                400,
            )

        #
        # TODO send emails
        #

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
