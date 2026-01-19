"""Email limiter utils."""

# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import arrow
from sqlalchemy import delete
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.constants import (
    EMAILS_LOG_STORAGE_CUTOFF,
    EMAILS_MAX_SENT_LAST_PERIOD,
    EMAILS_PERIOD_DAYS,
)
from app.models.email_log import EmailLog


def is_email_sending_allowed(recipient_email: str) -> bool:
    """Check if recipient has reached the mail limit

    See constants:
        EMAILS_MAX_SENT_LAST_PERIOD -> 20
        EMAILS_PERIOD_DAYS -> 7 days
    ."""

    recipient_email = recipient_email.lower().strip()

    db_session = container.get(scoped_session)
    now = arrow.now("Europe/Paris")
    period_start = now.shift(days=-EMAILS_PERIOD_DAYS)

    emails_sent_period = (
        db_session.query(EmailLog)
        .filter(
            EmailLog.recipient_email == recipient_email,
            EmailLog.sent_at >= period_start,
        )
        .count()
    )

    return emails_sent_period < EMAILS_MAX_SENT_LAST_PERIOD


def email_log_recipient(recipient_email: str) -> None:
    """Increment the count of sent mails for recipient.

    Also clean the back log."""

    recipient_email = recipient_email.lower().strip()
    now = arrow.now("Europe/Paris")
    cleanup_limit = now.shift(days=-EMAILS_LOG_STORAGE_CUTOFF)

    db_session = container.get(scoped_session)

    stmt = delete(EmailLog).where(
        EmailLog.recipient_email == recipient_email,
        EmailLog.sent_at < cleanup_limit,
    )
    db_session.execute(stmt)

    mail_log = EmailLog(
        recipient_email=recipient_email,
        sent_at=now,
    )

    db_session.add(mail_log)
    db_session.flush()
