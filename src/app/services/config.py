"""Configuration service for accessing Flask app configuration."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from flask import current_app
from flask_super.decorators import service


@service
class Config:
    """Config service that gives access to the current app config."""

    _config: dict[str, Any]

    def __init__(self) -> None:
        """Initialize config service with current app configuration."""
        self._config = current_app.config

    def __getitem__(self, key):
        """Get configuration value by key.

        Args:
            key: Configuration key.

        Returns:
            Configuration value.
        """
        return self._config[key]
