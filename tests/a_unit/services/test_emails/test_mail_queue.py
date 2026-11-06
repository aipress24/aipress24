# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mail goes through the queue, so an SMTP outage delays it instead of losing it."""

from __future__ import annotations

from smtplib import SMTPAuthenticationError
from typing import TYPE_CHECKING

import dramatiq
import pytest
import sqlalchemy as sa
from dramatiq.brokers.stub import StubBroker
from loguru import logger
from sqlalchemy.exc import OperationalError

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

if TYPE_CHECKING:
    from collections.abc import Iterator

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
def queueing(monkeypatch) -> Iterator[StubBroker]:
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
    return db.session.execute(
        sa.select(sa.func.count())
        .select_from(EmailLog)
        .where(EmailLog.recipient_email == RECIPIENT)
    ).scalar_one()


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


def test_inline_delivery_lets_smtp_failure_reach_the_caller(smtp, app_context) -> None:
    """No worker to retry under a stub broker."""
    smtp.error = OSError("network unreachable")

    with pytest.raises(OSError, match="network unreachable"):
        ParrainageMail(**KWARGS).send()


def test_a_failed_attempt_logs_below_the_level_sentry_captures(
    smtp, app_context
) -> None:
    smtp.error = OSError("network unreachable")
    errors = []
    sink = logger.add(errors.append, level="ERROR")

    with pytest.raises(OSError, match="network unreachable"):
        ParrainageMail(**KWARGS).deliver()

    logger.remove(sink)
    assert errors == []


def test_the_suite_refuses_what_the_queue_could_not_carry(smtp, app_context) -> None:
    with pytest.raises(TypeError):
        ParrainageMail(**{**KWARGS, "sender_full_name": object()}).send()


@pytest.mark.parametrize(
    ("retries", "exception", "expected"),
    [
        (0, SMTPAuthenticationError(535, b"bad key"), True),
        (0, TimeoutError(), True),
        (0, OperationalError("SELECT 1", {}, Exception("gone")), True),
        (MAX_RETRIES - 1, OSError(), True),
        (MAX_RETRIES, OSError(), False),
        (0, TypeError("wrong kwargs"), False),
    ],
)
def test_only_transient_failures_are_retried(retries, exception, expected) -> None:
    assert should_retry(retries, exception) is expected


def test_only_the_first_failure_raises_the_alarm(capsys) -> None:
    should_retry(0, OSError("smtp is down"))
    assert "smtp is down" in capsys.readouterr().err

    should_retry(1, OSError("smtp is down"))
    assert capsys.readouterr().err == ""


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
