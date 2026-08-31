# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/crud/cbvs/events.py - EventsTable behavior."""

from __future__ import annotations

import arrow

from app.models.lifecycle import PublicationStatus
from app.modules.wip.crud.cbvs.events import EventsTable
from app.modules.wip.models.eventroom import Event


class _Item:
    """Minimal stand-in for an Event row used by EventsTable.get_actions.

    The SUT reads ``id`` (for URL building), ``status`` (publish vs.
    unpublish) and the two cancellation predicates (ANN-01).

    Ces deux prédicats sont **empruntés à `Event`**, pas réécrits : ils
    ne lisent que `status` et `cancelled_at`, et une copie de la règle
    dans un double de test ne prouverait que la copie.
    """

    RESTORE_WINDOW_HOURS = Event.RESTORE_WINDOW_HOURS
    can_cancel = Event.can_cancel
    can_restore = Event.can_restore

    def __init__(
        self,
        id: int,
        status: PublicationStatus,
        cancelled_at: arrow.Arrow | None = None,
        publisher=None,
    ) -> None:
        self.id = id
        self.status = status
        self.cancelled_at = cancelled_at
        # REL-02/REL-03 : sans organisation éditrice, il n'y a personne
        # pour relire, et le parcours par défaut s'applique.
        self.publisher = publisher


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

        assert "Draft" in labels
        assert "Modifier" in labels
        assert "Images" in labels
        assert "Supprimer" in labels


class TestCancellationActions:
    """ANN-01 — quand « Annuler » et « Rétablir » sont proposés."""

    def test_published_event_can_be_cancelled(self):
        table = EventsTable()
        item = _Item(id=1, status=PublicationStatus.PUBLIC)

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Annuler l'événement" in labels
        assert "Rétablir l'événement" not in labels

    def test_draft_event_offers_neither(self):
        """Un brouillon n'a été annoncé à personne : rien à annuler."""
        table = EventsTable()
        item = _Item(id=1, status=PublicationStatus.DRAFT)

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Annuler l'événement" not in labels
        assert "Rétablir l'événement" not in labels

    def test_cancelled_event_offers_restore_within_the_window(self):
        table = EventsTable()
        item = _Item(
            id=1,
            status=PublicationStatus.PUBLIC,
            cancelled_at=arrow.utcnow().shift(hours=-23),
        )

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Rétablir l'événement" in labels
        assert "Annuler l'événement" not in labels

    def test_a_stale_cancellation_offers_nothing(self):
        """ANN-07 — passé 24 h, l'annulation est un fait acquis."""
        table = EventsTable()
        item = _Item(
            id=1,
            status=PublicationStatus.PUBLIC,
            cancelled_at=arrow.utcnow().shift(hours=-25),
        )

        labels = [a["label"] for a in table.get_actions(item)]

        assert "Rétablir l'événement" not in labels
        assert "Annuler l'événement" not in labels
