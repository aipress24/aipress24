# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for services/config.py"""

from __future__ import annotations

import pytest

from app.services.config import Config


def test_config_accesses_flask_config(app) -> None:
    """Test Config provides access to Flask configuration."""
    with app.app_context():
        config = Config()

        # DEBUG should be defined in test config
        assert isinstance(config["DEBUG"], bool)
        assert isinstance(config["TESTING"], bool)


def test_config_raises_key_error_for_missing(app) -> None:
    """Test Config raises KeyError for missing key."""
    with app.app_context():
        config = Config()

        with pytest.raises(KeyError):
            _ = config["NONEXISTENT_KEY_12345"]
