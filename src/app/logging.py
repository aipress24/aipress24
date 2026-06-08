"""Logging configuration using Loguru."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import contextlib
import sys
from typing import Any

import sentry_sdk
from loguru import logger

config = {
    "handlers": [
        {
            "sink": sys.stdout,
            "level": "INFO",
        },
        # {"sink": "file.log", "serialize": True},
    ],
}


def configure_logging() -> None:
    """Configure logging with Loguru.

    Sets up logging configuration and disables dramatiq logging.
    """
    logger.configure(**config)  # type: ignore[arg-type]
    logger.disable("app.dramatiq")


def warn(*args: Any) -> None:
    """Debug function to display infos on local terminal"""
    print("///// ", " ".join(str(x) for x in args), file=sys.stderr)


def report_failure(message: str, exc: BaseException) -> None:
    """Report a non-fatal failure : log it locally AND send to Sentry.

    Use in `except` blocks that intentionally swallow an exception so
    the surrounding state stays consistent (e.g. a state change must
    not be undone because an out-of-band notification or email fails).
    Silent swallow + warn-only is unfriendly to ops — nobody reads the
    logs. Sentry surfaces these in the alert stream.

    When Sentry isn't initialised (dev / tests without a DSN),
    `capture_exception` is a no-op, so this is safe to call from any
    runtime. A Sentry transport error is itself swallowed — the helper
    is called from already-defensive code paths, and a Sentry hiccup
    must not corrupt the caller's recovery.
    """
    warn(f"{message}: {exc}")
    # Telemetry must not corrupt the caller's recovery — Sentry's
    # transport may fail in dev / offline / misconfigured setups.
    with contextlib.suppress(Exception):
        sentry_sdk.capture_exception(exc)
