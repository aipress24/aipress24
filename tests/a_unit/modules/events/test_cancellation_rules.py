# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Transitions d'annulation — lot C2, règles pures.

`ANN-01`, `ANN-03` et `ANN-07` de `specs/events-complements.md` §4.
Aucune base ici : les trois règles ne lisent que `status` et
`cancelled_at`, et `Event.restore` prend `now` en paramètre — le seul
moyen d'éprouver une fenêtre de 24 heures dans un dépôt qui ne sait pas
geler le temps.
"""

from __future__ import annotations

import arrow
import pytest

from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.eventroom import Event


def _published() -> Event:
    event = Event(titre="Salon annulable")
    event.status = PublicationStatus.PUBLIC
    return event


class TestWhatCanBeCancelled:
    """ANN-01 — seul un événement publié et non déjà annulé."""

    def test_a_published_event_can_be_cancelled(self) -> None:
        assert _published().can_cancel()

    def test_a_draft_cannot(self) -> None:
        """Un brouillon n'a été annoncé à personne."""
        event = Event(titre="Brouillon")
        event.status = PublicationStatus.DRAFT

        assert not event.can_cancel()
        with pytest.raises(ValueError, match="pas publié"):
            event.cancel()

    def test_cancelling_twice_is_refused(self) -> None:
        event = _published()
        event.cancel("Grève des transports")

        assert not event.can_cancel()
        with pytest.raises(ValueError, match="déjà annulé"):
            event.cancel()


class TestCancellationLeavesEverythingElseAlone:
    """ANN-03 — l'annonce reste publique, elle se barre."""

    def test_the_status_does_not_move(self) -> None:
        event = _published()
        event.cancel("Salle indisponible")

        assert event.status == PublicationStatus.PUBLIC
        assert event.cancelled_at is not None
        assert event.cancellation_reason == "Salle indisponible"

    def test_the_reason_is_optional(self) -> None:
        """ANN-02 — facultatif, et vide plutôt que `None`."""
        event = _published()
        event.cancel()

        assert event.cancellation_reason == ""

    def test_an_overlong_reason_is_refused(self) -> None:
        """ANN-02 — 280 signes. L'écran est un formulaire HTML nu :
        cette garde **est** la validation, il n'y en a pas d'autre."""
        event = _published()

        with pytest.raises(ValueError, match="280"):
            event.cancel("x" * 281)

        assert event.cancelled_at is None, "un refus ne doit rien écrire"

    def test_the_reason_is_stripped(self) -> None:
        event = _published()
        event.cancel("  Grève  ")

        assert event.cancellation_reason == "Grève"


class TestTheRestoreWindow:
    """ANN-07 — 24 heures, puis l'annulation est un fait acquis."""

    def test_restoring_at_h23_is_accepted(self) -> None:
        event = _published()
        cancelled = arrow.utcnow()
        event.cancel("Erreur de date", now=cancelled)

        event.restore(now=cancelled.shift(hours=23))

        assert event.cancelled_at is None
        assert event.cancellation_reason == ""

    def test_restoring_at_h25_is_refused(self) -> None:
        event = _published()
        cancelled = arrow.utcnow()
        event.cancel("Erreur de date", now=cancelled)

        with pytest.raises(ValueError, match="plus de 24 heures"):
            event.restore(now=cancelled.shift(hours=25))

        assert event.cancelled_at == cancelled, "un refus ne doit rien écrire"

    def test_the_boundary_is_inclusive(self) -> None:
        event = _published()
        cancelled = arrow.utcnow()
        event.cancel(now=cancelled)

        event.restore(now=cancelled.shift(hours=24))

        assert event.cancelled_at is None

    def test_restoring_what_was_never_cancelled_is_refused(self) -> None:
        event = _published()

        assert not event.can_restore()
        with pytest.raises(ValueError, match="n'est pas annulé"):
            event.restore()


class TestUnpublishingClearsTheCancellation:
    """Sans quoi une republication ressusciterait un événement barré,
    avec un `cancelled_at` trop vieux pour être levé — un état dont
    plus rien ne permet de sortir."""

    def test_unpublish_wipes_it(self) -> None:
        event = _published()
        event.cancel("Reporté")

        event.unpublish()

        assert event.status == PublicationStatus.DRAFT
        assert event.cancelled_at is None
        assert event.cancellation_reason == ""

    def test_and_the_event_can_then_be_published_again(self) -> None:
        event = _published()
        event.titre = "Salon"
        event.contenu = "<p>Programme</p>"
        event.start_time = arrow.utcnow().shift(days=5).datetime
        event.end_time = arrow.utcnow().shift(days=6).datetime
        # MOD-01 : le mode par défaut exige une adresse pour publier.
        event.address = "1 rue de la Paix, Paris"
        event.cancel("Reporté")
        event.unpublish()

        event.publish()

        assert event.status == PublicationStatus.PUBLIC
        assert event.can_cancel(), "l'événement republié repart annulable"
