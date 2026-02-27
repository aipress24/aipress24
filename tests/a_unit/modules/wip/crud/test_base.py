# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for WIP CRUD base classes."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    pass


class TestGetNameHelper:
    """Tests for the get_name helper function."""

    def test_get_name_with_object(self):
        """Test get_name returns name when object has name."""
        from app.modules.wip.crud.cbvs._base import get_name

        obj = MagicMock()
        obj.name = "Test Organization"
        assert get_name(obj) == "Test Organization"

    def test_get_name_with_none(self):
        """Test get_name returns empty string for None."""
        from app.modules.wip.crud.cbvs._base import get_name

        assert get_name(None) == ""


class TestTemplateConstants:
    """Tests for template constants."""

    def test_list_template_defined(self):
        """Test LIST_TEMPLATE is defined."""
        from app.modules.wip.crud.cbvs._base import LIST_TEMPLATE

        assert "{% extends" in LIST_TEMPLATE
        assert "table.render()" in LIST_TEMPLATE

    def test_update_template_defined(self):
        """Test UPDATE_TEMPLATE is defined."""
        from app.modules.wip.crud.cbvs._base import UPDATE_TEMPLATE

        assert "{% extends" in UPDATE_TEMPLATE
        assert "form_rendered" in UPDATE_TEMPLATE

    def test_view_template_defined(self):
        """Test VIEW_TEMPLATE is defined."""
        from app.modules.wip.crud.cbvs._base import VIEW_TEMPLATE

        assert "{% extends" in VIEW_TEMPLATE
        assert "form_rendered" in VIEW_TEMPLATE


class TestBaseWipViewAttributes:
    """Tests for BaseWipView class attributes."""

    def test_route_prefix(self):
        """Test route_prefix is set correctly."""
        from app.modules.wip.crud.cbvs._base import BaseWipView

        assert BaseWipView.route_prefix == "/wip/"

    def test_required_attributes_defined(self):
        """Test that required attributes are declared."""
        from app.modules.wip.crud.cbvs._base import BaseWipView

        # Check type annotations exist
        assert "name" in BaseWipView.__annotations__
        assert "model_class" in BaseWipView.__annotations__
        assert "form_class" in BaseWipView.__annotations__
        assert "repo_class" in BaseWipView.__annotations__
        assert "table_class" in BaseWipView.__annotations__
        assert "doc_type" in BaseWipView.__annotations__

    def test_ui_attributes_defined(self):
        """Test that UI attributes are declared."""
        from app.modules.wip.crud.cbvs._base import BaseWipView

        # Check UI attribute annotations exist
        assert "label_main" in BaseWipView.__annotations__
        assert "label_list" in BaseWipView.__annotations__
        assert "label_new" in BaseWipView.__annotations__
        assert "label_edit" in BaseWipView.__annotations__
        assert "label_view" in BaseWipView.__annotations__
        assert "icon" in BaseWipView.__annotations__
