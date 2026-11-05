# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dramatiq actors: mail delivery, retried while SMTP fails."""

from __future__ import annotations

from app.dramatiq.job import job
from app.flask.extensions import db
from app.logging import report_failure

#: With the backoff below, about a day: long enough to outlast an SMTP outage.
MAX_RETRIES = 30
MIN_BACKOFF_MS = 60_000
MAX_BACKOFF_MS = 3_600_000


def should_retry(retries: int, exception: BaseException) -> bool:
    """Retry SMTP and network failures. Anything else is a programming error."""
    return isinstance(exception, OSError) and retries < MAX_RETRIES


@job(
    retry_when=should_retry,
    min_backoff=MIN_BACKOFF_MS,
    max_backoff=MAX_BACKOFF_MS,
    on_retry_exhausted="report_undelivered_mail",
)
def deliver_mail(mailer_name: str, mailer_kwargs: dict) -> None:
    """Send the mail described by the arguments of `EmailTemplate.send()`."""
    from app.services import emails

    mailer = getattr(emails, mailer_name)
    mailer(**mailer_kwargs).deliver()
    db.session.commit()


@job()
def report_undelivered_mail(message: dict, retry_info: dict) -> None:
    """Tell a person that a mail was given up on, since its sender cannot know."""
    mailer_name, mailer_kwargs = message["args"]
    last_error = message["options"]["traceback"].strip().splitlines()[-1]
    # The address goes to the log, not to Sentry.
    report_failure(
        f"Mail abandoned after {retry_info['retries']} retries, "
        f"to {mailer_kwargs['recipient']!r} ({last_error})",
        RuntimeError(f"Undelivered mail: {mailer_name}"),
    )
