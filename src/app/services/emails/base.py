# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass, fields
from importlib import resources as rso
from smtplib import SMTPException

from flask import render_template_string
from flask_mailman import EmailMessage
from loguru import logger
from markdown import markdown

from . import mail_templates
from .email_limiter import count_recipient_mails, is_email_sending_allowed


@dataclass(kw_only=True)
class EmailTemplate:
    sender: str
    recipient: str
    sender_mail: str
    subject: str = ""
    template_md: str = ""
    template_html: str = ""
    bypass_quota: bool = False

    def __post_init__(self) -> None:
        self.ctx = {f.name: getattr(self, f.name) for f in fields(self)}

    def _render_md(self) -> str:
        body = rso.read_text(mail_templates, self.template_md)
        content = render_template_string(body, **self.ctx)
        return markdown(content)

    def _render_html(self) -> str:
        body = rso.read_text(mail_templates, self.template_html)
        content = render_template_string(body, **self.ctx)
        return content

    @property
    def logged_informations(self) -> str:
        """Return the mail specific information logged"""
        return ", ".join(
            [
                f"sender: {self.sender!r}",
                f"sender_mail: {self.sender_mail!r}",
                f"recipient: {self.recipient!r}",
                f"subject: {self.subject!r}",
            ]
        )

    def render(self) -> str:
        if self.template_md:
            return self._render_md()
        if self.template_html:
            return self._render_html()
        msg = "No mail template"
        raise ValueError(msg)

    def send(self) -> bool:
        if self.bypass_quota or is_email_sending_allowed(self.recipient):
            result = self._send_mail()
            if result:
                count_recipient_mails(self.recipient)
        else:
            msg = f"Mail quota exceeded for recipient: {self.recipient!r}"
            logger.error(msg)
            result = False
        return result

    def _send_mail(self) -> bool:
        # subject='',
        # body='',
        # from_email=None,
        # to=None,
        # bcc=None,
        # connection=None,
        # attachments=None,
        # headers=None,
        # cc=None,
        # reply_to=None,
        message = EmailMessage(
            subject=self.subject,
            body=self.render(),
            from_email=self.sender,  # or config default?
            to=[self.recipient],
        )
        message.content_subtype = "html"
        try:
            message.send()
            logger.info(
                f"Mail success: {self.__class__.__name__} {self.logged_informations}"
            )
            return True
        except SMTPException as e:
            msg = f"Mail error: (SMTP error {e}), {self.logged_informations}"
            logger.error(msg)
            return False
