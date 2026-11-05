# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mail goes through the queue, so an SMTP outage delays it instead of losing it."""

from __future__ import annotations

from smtplib import SMTPAuthenticationError

import dramatiq
import pytest
import sqlalchemy as sa
from dramatiq.brokers.stub import StubBroker

from app.actors.emails import (
    MAX_RETRIES,
    deliver_mail,
    report_undelivered_mail,
    should_retry,
)
from app.constants import EMAILS_MAX_SENT_LAST_PERIOD
from app.flask.extensions import db
from app.models.email_log import EmailLog
from app.services import emails
from app.services.emails import base
from app.services.emails.base import EmailTemplate
from app.services.emails.mailers import ParrainageMail

RECIPIENT = "queued@example.com"
KWARGS = {
    "sender": "contact@aipress24.com",
    "recipient": RECIPIENT,
    "sender_mail": "someone@example.com",
    "sender_full_name": "Someone",
}


class StubEmailMessage:
    """Records what would have left, or fails like SMTP does."""

    sent: list[StubEmailMessage]
    error: Exception | None = None

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.content_subtype = "plain"

    def send(self) -> None:
        if self.error:
            raise self.error
        self.sent.append(self)


@pytest.fixture
def smtp(monkeypatch) -> type[StubEmailMessage]:
    StubEmailMessage.sent = []
    StubEmailMessage.error = None
    monkeypatch.setattr(base, "EmailMessage", StubEmailMessage)
    return StubEmailMessage


@pytest.fixture
def queueing(monkeypatch) -> StubBroker:
    """The production path, on the stub broker the test app already has."""
    monkeypatch.setattr(base, "_delivers_inline", lambda: False)
    broker = dramatiq.get_broker()
    assert isinstance(broker, StubBroker)
    broker.flush_all()
    yield broker
    broker.flush_all()


@pytest.fixture(autouse=True)
def forget_log_rows():
    """`deliver_mail` commits, which the test transaction cannot undo."""
    yield
    db.session.rollback()
    db.session.execute(sa.delete(EmailLog).where(EmailLog.recipient_email == RECIPIENT))
    db.session.commit()


def _logged() -> int:
    return db.session.scalar(
        sa.select(sa.func.count())
        .select_from(EmailLog)
        .where(EmailLog.recipient_email == RECIPIENT)
    )


def test_send_queues_instead_of_contacting_smtp(smtp, queueing) -> None:
    assert ParrainageMail(**KWARGS).send() is True

    assert smtp.sent == []
    [message] = list(queueing.queues[deliver_mail.queue_name].queue)
    assert b"ParrainageMail" in message
    assert RECIPIENT.encode() in message


def test_worker_sends_and_keeps_the_log_row(smtp, app_context) -> None:
    deliver_mail("ParrainageMail", KWARGS)
    db.session.rollback()

    assert [m.kwargs["to"] for m in smtp.sent] == [[RECIPIENT]]
    assert _logged() == 1


def test_smtp_failure_reaches_dramatiq_and_logs_nothing(smtp, app_context) -> None:
    smtp.error = SMTPAuthenticationError(535, b"bad key")

    with pytest.raises(SMTPAuthenticationError):
        deliver_mail("ParrainageMail", KWARGS)

    assert _logged() == 0


def test_over_quota_gives_up_without_retry(smtp, app_context) -> None:
    db.session.add_all(
        EmailLog(recipient_email=RECIPIENT) for _ in range(EMAILS_MAX_SENT_LAST_PERIOD)
    )
    db.session.flush()

    deliver_mail("ParrainageMail", KWARGS)

    assert smtp.sent == []


def test_inline_delivery_swallows_smtp_failure(smtp, app_context) -> None:
    """No worker to retry under a stub broker: the caller just gets `False`."""
    smtp.error = OSError("network unreachable")

    assert ParrainageMail(**KWARGS).send() is False


def test_inline_delivery_refuses_what_the_broker_could_not_carry(
    smtp, app_context
) -> None:
    with pytest.raises(TypeError):
        ParrainageMail(**{**KWARGS, "sender_full_name": object()}).send()


@pytest.mark.parametrize(
    ("retries", "exception", "expected"),
    [
        (0, SMTPAuthenticationError(535, b"bad key"), True),
        (0, TimeoutError(), True),
        (MAX_RETRIES - 1, OSError(), True),
        (MAX_RETRIES, OSError(), False),
        (0, TypeError("wrong kwargs"), False),
    ],
)
def test_only_smtp_and_network_failures_are_retried(
    retries, exception, expected
) -> None:
    assert should_retry(retries, exception) is expected


def test_actor_options_reach_the_broker() -> None:
    broker = dramatiq.get_broker()
    options = broker.get_actor("deliver_mail").options

    assert options["retry_when"] is should_retry
    assert broker.get_actor(options["on_retry_exhausted"])


def test_abandoned_mail_is_reported_with_its_recipient_in_the_log(capsys) -> None:
    report_undelivered_mail(
        {
            "args": ["ParrainageMail", KWARGS],
            "options": {"traceback": "Traceback…\nTimeoutError: timed out\n"},
        },
        {"retries": MAX_RETRIES, "max_retries": None},
    )

    err = capsys.readouterr().err
    assert RECIPIENT in err
    assert "TimeoutError: timed out" in err


def test_the_actor_can_rebuild_every_mailer() -> None:
    def subclasses(cls: type) -> set[type]:
        direct = set(cls.__subclasses__())
        return direct.union(*(subclasses(sub) for sub in direct))

    missing = {
        mailer.__name__
        for mailer in subclasses(EmailTemplate)
        if mailer.__module__.startswith("app.") and not hasattr(emails, mailer.__name__)
    }
    assert not missing
