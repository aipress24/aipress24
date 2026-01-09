# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import smtplib
from pathlib import Path

from boltons.strutils import html2text
from flask import current_app, render_template
from flask_mailman import EmailMessage
from flask_super.decorators import service
from jinja2 import Environment
from loguru import logger

from .mailers import (
    AvisEnqueteNotificationMail,
    BWInvitationMail,
    ContactAvisEnqueteAcceptanceMail,
)

__all__ = [
    "ALERTS_RECIPIENTS",
    "AvisEnqueteNotificationMail",
    "BWInvitationMail",
    "ContactAvisEnqueteAcceptanceMail",
    "EmailService",
]

ALERTS_RECIPIENTS = ["test@aipress24.com"]


@service
class EmailService:
    def send_system_email(
        self, msg: str, subject: str = "Aipress24 system message"
    ) -> None:
        try:
            message = EmailMessage(subject=subject, to=ALERTS_RECIPIENTS, body=msg)
            message.send()
        except smtplib.SMTPException:
            logger.exception("Failed to send system email")


def _generate_email(data: dict, template: str | Path) -> tuple[str, str]:
    if Path(template).is_absolute():
        template_str = Path(template).read_text()
    else:
        template_str = (Path(__file__).parent / "templates" / template).read_text()

    jinja_env: Environment = current_app.jinja_env
    jinja_template = jinja_env.from_string(template_str)
    html = render_template(jinja_template, **data)

    text = html2text(html)

    return html, text


# def send_email(
#     recipients: list[str],
#     subject: str,
#     body: str,
#     html: str | None = None,
# ) -> None:
#     message = EmailMultiAlternatives(subject=subject, to=recipients, body=body)
#     message.attach_alternative(html, "text/html")
#     message.send()
