# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/crud/cbvs/communiques.py - CommuniquesTable behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.lifecycle import PublicationStatus
from app.modules.wip.crud.cbvs.communiques import CommuniquesTable, CommuniquesWipView


class TestCommuniquesTableActions:
    """Test CommuniquesTable.get_actions behavior based on publication status."""

    def test_draft_item_shows_publish_action(self):
        """Draft items should have 'Publier' but not 'Dépublier'."""
        table = CommuniquesTable()
        item = MagicMock(id=1, status=PublicationStatus.DRAFT)

        actions = table.get_actions(item)
        labels = [a["label"] for a in actions]

        assert "Publier" in labels
        assert "Dépublier" not in labels

    def test_published_item_shows_unpublish_action(self):
        """Published items should have 'Dépublier' but not 'Publier'."""
        table = CommuniquesTable()
        item = MagicMock(id=1, status=PublicationStatus.PUBLIC)

        actions = table.get_actions(item)
        labels = [a["label"] for a in actions]

        assert "Dépublier" in labels
        assert "Publier" not in labels

    def test_all_items_have_core_actions(self):
        """All items should have view, edit, images, and delete actions."""
        table = CommuniquesTable()
        item = MagicMock(id=1, status=PublicationStatus.DRAFT)

        actions = table.get_actions(item)
        labels = [a["label"] for a in actions]

        assert "Voir" in labels
        assert "Modifier" in labels
        assert "Images" in labels
        assert "Supprimer" in labels


class TestExtraViewHtml:
    """Bug 0128: in view ("Voir") mode, the CP gallery must be rendered below
    the form so RP authors can confirm the images attached to their CP."""

    def test_returns_empty_string_in_edit_mode(self, app):
        """Edit mode keeps the dedicated /images/ page; gallery only on view."""
        view = CommuniquesWipView()
        model = SimpleNamespace(
            sorted_images=[
                SimpleNamespace(
                    url="/img/1.png", caption="x", copyright="(c)", position=0
                )
            ]
        )
        with app.test_request_context():
            assert view._extra_view_html(model, mode="edit") == ""

    def test_returns_empty_string_when_no_images(self, app):
        view = CommuniquesWipView()
        model = SimpleNamespace(sorted_images=[])
        with app.test_request_context():
            assert view._extra_view_html(model, mode="view") == ""

    def test_returns_empty_string_when_model_is_none(self, app):
        view = CommuniquesWipView()
        with app.test_request_context():
            assert view._extra_view_html(None, mode="view") == ""

    def test_renders_gallery_in_view_mode(self, app):
        view = CommuniquesWipView()
        model = SimpleNamespace(
            sorted_images=[
                SimpleNamespace(
                    url="/img/cp1.png",
                    caption="First image",
                    copyright="© Igor",
                    position=0,
                ),
                SimpleNamespace(
                    url="/img/cp2.png",
                    caption="Second image",
                    copyright="© Igor",
                    position=1,
                ),
            ]
        )
        with app.test_request_context():
            html = view._extra_view_html(model, mode="view")

        assert "/img/cp1.png" in html
        assert "/img/cp2.png" in html
        assert "First image" in html
        assert "Second image" in html
        # Gallery section header so the user understands what they see.
        assert "Images" in html

    def test_caption_falls_back_to_default(self, app):
        view = CommuniquesWipView()
        model = SimpleNamespace(
            sorted_images=[
                SimpleNamespace(url="/img/x.png", caption="", copyright="", position=0)
            ]
        )
        with app.test_request_context():
            html = view._extra_view_html(model, mode="view")

        assert "Pas de description" in html
        assert "Pas de mention de copyright" in html
