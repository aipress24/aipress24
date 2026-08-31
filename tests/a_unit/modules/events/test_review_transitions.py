# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Relecture éditoriale — lot C9, transitions du modèle.

`REL-01`, `REL-02` et `REL-04` de `specs/events-complements.md` §5. Le
cycle devient `DRAFT → PENDING → PUBLIC`, avec `PENDING → DRAFT` en cas
de renvoi.

Aucune valeur n'est ajoutée à `PublicationStatus` : `PENDING` existe et
sert déjà aux annonces de la place de marché. Seul le circuit est
nouveau.
"""

from __future__ import annotations

import arrow
import pytest

from app.enums import EventMode, EventPricing
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models.eventroom import Event


def _draft(**overrides) -> Event:
    event = Event(titre="Salon", contenu="<p>Programme</p>")
    event.status = PublicationStatus.DRAFT
    event.mode = EventMode.ON_SITE
    event.address = "1 rue de la Paix, Paris"
    event.pricing = EventPricing.FREE_FOR_ALL
    event.start_time = arrow.utcnow().shift(days=5).datetime
    event.end_time = arrow.utcnow().shift(days=6).datetime
    for key, value in overrides.items():
        setattr(event, key, value)
    return event


class TestSubmitting:
    """REL-01 — `DRAFT → PENDING`."""

    def test_a_draft_goes_to_review(self) -> None:
        event = _draft()

        event.submit_for_review()

        assert event.status == PublicationStatus.PENDING

    def test_and_nothing_else_does(self) -> None:
        for status in (PublicationStatus.PENDING, PublicationStatus.PUBLIC):
            event = _draft(status=status)

            assert not event.can_submit_for_review()
            with pytest.raises(ValueError, match="seul un brouillon"):
                event.submit_for_review()


class TestSubmittingChecksTheSameThingsAsPublishing:
    """REL-04 — un relecteur ne doit pas hériter d'un brouillon
    impubliable : il n'aurait alors le choix qu'entre le renvoyer pour
    un défaut que l'auteur ne voyait pas, ou le valider vers un échec.
    """

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"titre": ""}, "titre"),
            ({"contenu": ""}, "contenu"),
            ({"start_time": None}, "date de début"),
            ({"address": ""}, "adresse"),
            (
                {"pricing": EventPricing.PAID, "price": None},
                "demande un prix",
            ),
        ],
    )
    def test_an_incomplete_draft_is_refused(self, overrides, message) -> None:
        event = _draft(**overrides)

        with pytest.raises(ValueError, match=message):
            event.submit_for_review()

        assert event.status == PublicationStatus.DRAFT, "un refus ne soumet rien"

    def test_the_same_defect_also_blocks_publication(self) -> None:
        """Le témoin : les deux portes appliquent bien la même règle."""
        event = _draft(address="")

        with pytest.raises(ValueError, match="adresse"):
            event.publish()


class TestSendingBack:
    """REL-02 — `PENDING → DRAFT`, avec un motif obligatoire."""

    def test_a_pending_event_returns_to_draft(self) -> None:
        event = _draft()
        event.submit_for_review()

        event.send_back("Il manque le nom de la salle.")

        assert event.status == PublicationStatus.DRAFT

    def test_the_comment_is_mandatory(self) -> None:
        """Un renvoi sans motif fait recommencer l'auteur à l'aveugle."""
        event = _draft()
        event.submit_for_review()

        for empty in ("", "   "):
            with pytest.raises(ValueError, match="motif"):
                event.send_back(empty)

        assert event.status == PublicationStatus.PENDING, "un refus ne renvoie rien"

    def test_only_a_pending_event_may_be_sent_back(self) -> None:
        event = _draft()

        assert not event.can_send_back()
        with pytest.raises(ValueError, match="pas en relecture"):
            event.send_back("Motif")


class TestPublishing:
    """REL-01 — `PENDING → PUBLIC`, et `DRAFT → PUBLIC` reste ouvert."""

    def test_a_reviewed_event_may_be_published(self) -> None:
        event = _draft()
        event.submit_for_review()

        event.publish()

        assert event.status == PublicationStatus.PUBLIC

    def test_and_a_draft_may_still_be_published_directly(self) -> None:
        """REL-03 à `False` reproduit le parcours actuel : un rôle
        habilité publie sans passer par la relecture."""
        event = _draft()

        event.publish()

        assert event.status == PublicationStatus.PUBLIC

    def test_but_a_published_event_may_not_be_published_again(self) -> None:
        event = _draft()
        event.publish()

        assert not event.can_publish()
