# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/config module."""

from __future__ import annotations

import pytest

from app.services.config import Config


class TestConfig:
    """Test suite for Config service."""

    def test_config_init(self, app, app_context):
        """Test Config service initialization."""
        config = Config()
        assert config._config is not None
        assert isinstance(config._config, dict)

    def test_config_getitem_existing_key(self, app_context):
        """Test getting existing configuration value."""
        config = Config()
        # TESTING is always set to True in test config
        result = config["TESTING"]
        assert result is True

    def test_config_getitem_custom_key(self, app, app_context):
        """Test getting custom configuration value."""
        app.config["CUSTOM_KEY"] = "custom_value"
        config = Config()
        result = config["CUSTOM_KEY"]
        assert result == "custom_value"

    def test_config_getitem_nonexistent_key(self, app_context):
        """Test that accessing nonexistent key raises KeyError."""
        config = Config()
        with pytest.raises(KeyError):
            _ = config["NONEXISTENT_KEY"]

    def test_config_getitem_with_none_value(self, app, app_context):
        """Test getting config key with None value."""
        app.config["NULL_KEY"] = None
        config = Config()
        result = config["NULL_KEY"]
        assert result is None

    def test_config_reflects_app_config_changes(self, app, app_context):
        """Test that Config reflects changes to app.config."""
        config = Config()
        app.config["DYNAMIC_KEY"] = "initial"
        assert config["DYNAMIC_KEY"] == "initial"

        # Modify app.config after Config initialization
        app.config["DYNAMIC_KEY"] = "updated"
        assert config["DYNAMIC_KEY"] == "updated"

    def test_config_getitem_with_different_types(self, app, app_context):
        """Test accessing config values of different types."""
        app.config["STRING_KEY"] = "string_value"
        app.config["INT_KEY"] = 42
        app.config["LIST_KEY"] = [1, 2, 3]
        app.config["DICT_KEY"] = {"nested": "value"}

        config = Config()

        assert config["STRING_KEY"] == "string_value"
        assert config["INT_KEY"] == 42
        assert config["LIST_KEY"] == [1, 2, 3]
        assert config["DICT_KEY"] == {"nested": "value"}
