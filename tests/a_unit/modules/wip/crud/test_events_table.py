# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/crud/cbvs/events.py - EventsTable behavior."""

from __future__ import annotations

from app.models.lifecycle import PublicationStatus
from app.modules.wip.crud.cbvs.events import EventsTable


class _Item:
    """Minimal stand-in for an Event row used by EventsTable.get_actions.

    The SUT only reads ``id`` (for URL building) and ``status`` (to choose
    publish vs. unpublish action).
    """

    def __init__(self, id: int, status: PublicationStatus) -> None:
        self.id = id
        self.status = status


class TestEventsTableActions:
    """Test EventsTable.get_actions behavior based on publication status."""

    def test_draft_item_shows_publish_action(self):
        """Draft items should have 'Publier' but not 'Dépublier'."""
        table = EventsTable()
        item = _Item(id=1, status=PublicationStatus.DRAFT)

        actions = table.get_actions(item)
        labels = [a["label"] for a in actions]

        assert "Publier" in labels
        assert "Dépublier" not in labels

    def test_published_item_shows_unpublish_action(self):
        """Published items should have 'Dépublier' but not 'Publier'."""
        table = EventsTable()
        item = _Item(id=1, status=PublicationStatus.PUBLIC)

        actions = table.get_actions(item)
        labels = [a["label"] for a in actions]

        assert "Dépublier" in labels
        assert "Publier" not in labels

    def test_all_items_have_core_actions(self):
        """All items should have view, edit, images, and delete actions."""
        table = EventsTable()
        item = _Item(id=1, status=PublicationStatus.DRAFT)

        actions = table.get_actions(item)
        labels = [a["label"] for a in actions]

        assert "Voir" in labels
        assert "Modifier" in labels
        assert "Images" in labels
        assert "Supprimer" in labels
