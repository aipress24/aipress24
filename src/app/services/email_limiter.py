"""Email limiter utils."""

# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import arrow
from sqlalchemy import delete
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.models.email_log import EmailLog

EMAIL_PERIOD_DAYS = 30
EMAILS_MAX_SENT_LAST_PERIOD = 20
EMAILS_LOG_STORAGE_CUTOFF = 90


def is_email_sending_allowed(recipient_email: str) -> bool:
    """Check if recipient has reached the mail limit (20 per month).

    Also clean the back log."""

    recipient_email = recipient_email.lower().strip()

    db_session = container.get(scoped_session)
    now = arrow.now("Europe/Paris")
    period_start = now.shift(days=-EMAIL_PERIOD_DAYS)
    cleanup_limit = now.shift(days=-EMAILS_LOG_STORAGE_CUTOFF)

    stmt = delete(EmailLog).where(
        EmailLog.recipient_email == recipient_email,
        EmailLog.sent_at < cleanup_limit,
    )
    db_session.execute(stmt)

    emails_sent_period = (
        db_session.query(EmailLog)
        .filter(
            EmailLog.recipient_email == recipient_email,
            EmailLog.sent_at >= period_start,
        )
        .count()
    )

    return emails_sent_period < EMAILS_MAX_SENT_LAST_PERIOD
