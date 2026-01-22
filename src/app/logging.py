"""Logging configuration using Loguru."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from typing import Any

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
