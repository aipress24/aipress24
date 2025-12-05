# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from importlib import resources as rso
from smtplib import SMTPException

from flask import render_template_string
from flask_mailman import EmailMessage
from loguru import logger
from markdown import markdown

from . import mail_templates
from .email_limiter import email_log_recipient, is_email_sending_allowed


class EmailTemplate:
    subject: str = ""
    template_md: str = ""
    template_html: str = ""

    def __init__(self, sender: str, recipient: str, **kwargs) -> None:
        self.sender = sender
        self.recipient = recipient
        self.kwargs = kwargs

    def _render_md(self) -> str:
        body = rso.read_text(mail_templates, self.template_md)
        content = render_template_string(body, **self.kwargs)
        return markdown(content)

    def _render_html(self) -> str:
        body = rso.read_text(mail_templates, self.template_html)
        content = render_template_string(body, **self.kwargs)
        return content

    def render(self) -> str:
        if self.template_md:
            return self._render_md()
        if self.template_html:
            return self._render_html()
        msg = "No mail template"
        raise ValueError(msg)

    def send(self) -> bool:
        if self.kwargs.get("force") or is_email_sending_allowed(self.recipient):
            result = self.send_mail()
            if result:
                email_log_recipient(self.recipient)
        else:
            msg = f"Mail quota exceeded for recipients: {self.recipient!r}"
            logger.error(msg)
            result = False
        return result

    def send_mail(self) -> bool:
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
            logger.info(f"Mail {self.__class__.__name__} sent to: {self.recipient!r}")
            return True
        except SMTPException as e:
            msg = f"Error for recipients: {self.recipient!r} :\nSMTP error {e}"
            logger.error(msg)
            return False
