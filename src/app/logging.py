"""Logging configuration using Loguru."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys

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
    print("Configuring logging")
    logger.configure(**config)
    logger.disable("app.dramatiq")
