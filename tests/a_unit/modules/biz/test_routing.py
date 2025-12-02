# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for biz/routing.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from werkzeug.routing.exceptions import BuildError

from app.flask.routing import url_for
from app.models.auth import User
from app.modules.biz import routing as biz_routing  # noqa: F401
from app.modules.biz.models import MarketplaceContent

if TYPE_CHECKING:
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy


class TestMarketplaceContentRouting:
    """Test suite for MarketplaceContent URL routing."""

    def test_url_for_biz_item_default(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test url_for_biz_item with default parameters."""
        user = User(email="test_biz_default@example.com")
        db.session.add(user)
        db.session.flush()

        item = MarketplaceContent(owner_id=user.id, type="product")
        db.session.add(item)
        db.session.flush()

        result = url_for(item)

        assert result is not None
        assert isinstance(result, str)
        assert "/biz/" in result

    def test_url_for_biz_item_with_kwargs(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test url_for_biz_item with additional kwargs passes them through."""
        user = User(email="test_biz_kwargs@example.com")
        db.session.add(user)
        db.session.flush()

        item = MarketplaceContent(owner_id=user.id, type="service")
        db.session.add(item)
        db.session.flush()

        result = url_for(item, tab="details")

        assert result is not None
        assert isinstance(result, str)
        # Query parameters should be included
        assert "tab=details" in result

    def test_url_for_biz_item_with_namespace(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test url_for_biz_item with custom namespace fails when route doesn't exist."""
        user = User(email="test_biz_namespace@example.com")
        db.session.add(user)
        db.session.flush()

        item = MarketplaceContent(owner_id=user.id, type="product")
        db.session.add(item)
        db.session.flush()

        # Custom namespace route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(item, _ns="custom")
