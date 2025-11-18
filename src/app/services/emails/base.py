# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from importlib import resources as rso

from flask import render_template_string
from flask_mailman import EmailMessage, Mail
from markdown import markdown

from . import mail_templates

# app = Flask(__name__)
# mail_instance = Mail(app)
#
# with app.app_context():
#     mail = BWInvitationMail(
#         sender="sender@example.com",
#         recipient="recipient@example.com",
#     )
#     mail.send(mail_instance)


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

    def send(self) -> None:
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
        mail_instance.send(message)


class BWInvitationMail(EmailTemplate):
    subject = "Invitation to join AiPRESS24"
    template_html = "bw_invitation.j2"
