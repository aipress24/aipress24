# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass, field, fields
from importlib import resources as rso
from typing import ClassVar

import dramatiq
from dramatiq.brokers.stub import StubBroker
from flask import render_template_string
from flask_mailman import EmailMessage
from loguru import logger
from markdown import markdown

from app.enums import NotificationCategory

from . import mail_templates
from ._preferences import recipient_wants
from .email_limiter import (
    count_recipient_mails,
    is_email_sending_allowed,
    mail_debug_active,
)


@dataclass(kw_only=True)
class EmailTemplate:
    sender: str
    recipient: str
    sender_mail: str
    subject: str = ""
    template_md: str = ""
    template_html: str = ""
    bypass_quota: bool = False

    #: PRF-02 — la famille de ce message, qui décide s'il est
    #: désactivable. Un `ClassVar` : il n'entre ni dans les champs de
    #: la dataclass ni dans le contexte du gabarit.
    #:
    #: Le défaut est **transactionnel**, c'est-à-dire toujours envoyé.
    #: Une classe qui oublie de déclarer sa famille part donc, plutôt
    #: que d'être supprimée en silence.
    category: ClassVar[NotificationCategory] = NotificationCategory.TRANSACTIONAL

    #: The context handed to the template: every dataclass field.
    #: `field(init=False)` keeps it out of the constructor signature.
    ctx: dict = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.ctx = {f.name: getattr(self, f.name) for f in fields(self) if f.init}

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
        """Hand this mail over for delivery. `False` if none will happen.

        `True` means accepted, not delivered: the worker sends it and
        retries while SMTP fails (`app.actors.emails`). Without a worker
        (see `_delivers_inline`), an SMTP failure reaches the caller.
        """
        if not recipient_wants(self.recipient, self.category):
            # PRF-05 — pas un incident : un réglage respecté. Journalisé
            # en `info`, et `False` parce que rien n'est parti — un
            # appelant qui compte ses envois doit compter juste.
            logger.info(
                f"Mail suppressed by preference: {self.__class__.__name__} "
                f"({self.category.value}) {self.logged_informations}"
            )
            return False

        if _delivers_inline():
            return self.deliver()

        from app.actors.emails import deliver_mail

        deliver_mail.send(self.__class__.__name__, self.ctx)
        return True

    def deliver(self) -> bool:
        """Send now. `False` over quota; raises `OSError` if SMTP fails."""
        if not (self.bypass_quota or is_email_sending_allowed(self.recipient)):
            msg = f"Mail quota exceeded for recipient: {self.recipient!r}"
            logger.error(msg)
            return False

        self._send_mail()
        count_recipient_mails(self.recipient)
        return True

    def _send_mail(self) -> None:
        message = EmailMessage(
            subject=self.subject,
            body=self.render(),
            from_email=self.sender,  # or config default?
            to=[self.recipient],
        )
        message.content_subtype = "html"
        try:
            message.send()
        except OSError as e:  # SMTPException is an OSError too
            msg = (
                f"Mail error: ({e.__class__.__name__}: {e}), {self.logged_informations}"
            )
            # Not `error`, which loguru sends to Sentry: the actor decides
            # when a failed attempt deserves an alarm.
            logger.warning(msg)
            raise
        logger.info(
            f"Mail success: {self.__class__.__name__} {self.logged_informations}"
        )


def _delivers_inline() -> bool:
    """Whether this process must send by itself instead of queueing.

    No worker reads a stub broker, and `MailDebug` keeps its outbox in the
    memory of the process that sends.
    """
    return isinstance(dramatiq.get_broker(), StubBroker) or mail_debug_active()
