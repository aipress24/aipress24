# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Affichage du tarif — `PRX-04`, et les règles de `publish()`.

Le libellé dépend du lecteur, ce qu'aucune autre information d'une
carte d'événement ne fait. Le tableau de la spécification a six cases ;
elles sont toutes ici.
"""

from __future__ import annotations

import arrow
import pytest

from app.enums import EventMode, EventPricing, RoleEnum
from app.models.lifecycle import PublicationStatus
from app.modules.events.pricing import is_journalist, price_label
from app.modules.wip.models.eventroom import Event


class _Event:
    """Le minimum que `price_label` lit."""

    def __init__(self, pricing, price=None, currency="EUR") -> None:
        self.pricing = pricing
        self.price = price
        self.currency = currency


class _User:
    """Un lecteur, avec ou sans la carte de presse."""

    is_anonymous = False

    def __init__(self, *roles) -> None:
        self._roles = set(roles)

    def has_role(self, role) -> bool:
        return role in self._roles


JOURNALIST = _User(RoleEnum.PRESS_MEDIA)
OTHER = _User(RoleEnum.EXPERT)


class TestTheSixCombinations:
    """Le tableau de `PRX-04`, case par case."""

    @pytest.mark.parametrize(
        ("pricing", "price", "reader", "expected"),
        [
            (EventPricing.FREE_FOR_ALL, None, JOURNALIST, "Gratuit"),
            (EventPricing.FREE_FOR_ALL, None, OTHER, "Gratuit"),
            (
                EventPricing.FREE_FOR_JOURNALISTS,
                4500,
                JOURNALIST,
                "Gratuit pour les journalistes",
            ),
            (
                EventPricing.FREE_FOR_JOURNALISTS,
                4500,
                OTHER,
                "45,00 € — gratuit pour les journalistes",
            ),
            (EventPricing.PAID, 4500, JOURNALIST, "45,00 €"),
            (EventPricing.PAID, 4500, OTHER, "45,00 €"),
        ],
    )
    def test_the_table(self, pricing, price, reader, expected) -> None:
        assert price_label(_Event(pricing, price), reader) == expected


class TestTheAnonymousReader:
    """Il lit la colonne « autre membre » : c'est ce qu'il paierait, et
    lui montrer « gratuit » serait un mensonge sur lequel il se
    déplacerait."""

    def test_a_journalists_free_event_shows_him_the_price(self) -> None:
        event = _Event(EventPricing.FREE_FOR_JOURNALISTS, 4500)

        assert price_label(event, None) == "45,00 € — gratuit pour les journalistes"

    def test_and_a_free_event_stays_free(self) -> None:
        assert price_label(_Event(EventPricing.FREE_FOR_ALL), None) == "Gratuit"


class TestTheJournalistPredicate:
    def test_a_journalist_is_one(self) -> None:
        assert is_journalist(JOURNALIST)

    def test_and_nobody_else(self) -> None:
        assert not is_journalist(OTHER)

    def test_anonymous_is_not(self) -> None:
        assert not is_journalist(None)

    def test_a_user_without_any_community_role_is_not(self) -> None:
        """`has_role` et non `first_community()` : celle-ci lève
        `RuntimeError` pour un administrateur ou un compte de service."""
        assert not is_journalist(_User())


class TestTheAmountIsFormatted:
    def test_centimes_become_euros(self) -> None:
        assert price_label(_Event(EventPricing.PAID, 4500), OTHER) == "45,00 €"

    def test_odd_centimes_survive(self) -> None:
        assert price_label(_Event(EventPricing.PAID, 4550), OTHER) == "45,50 €"

    def test_one_centime_is_not_lost(self) -> None:
        assert price_label(_Event(EventPricing.PAID, 1), OTHER) == "0,01 €"

    def test_another_currency_is_honoured(self) -> None:
        event = _Event(EventPricing.PAID, 4500, currency="USD")

        assert "45,00" in price_label(event, OTHER)
        assert "€" not in price_label(event, OTHER)


def _publishable(pricing=EventPricing.FREE_FOR_ALL, price=None) -> Event:
    event = Event(titre="Salon", contenu="<p>Programme</p>", pricing=pricing)
    event.status = PublicationStatus.DRAFT
    event.mode = EventMode.ON_SITE
    event.address = "1 rue de la Paix, Paris"
    event.start_time = arrow.utcnow().shift(days=5).datetime
    event.end_time = arrow.utcnow().shift(days=6).datetime
    event.price = price
    return event


class TestPublishingWithAPrice:
    """PRX-02 — un tarif payant exige un prix strictement positif."""

    @pytest.mark.parametrize(
        "pricing",
        [EventPricing.PAID, EventPricing.FREE_FOR_JOURNALISTS],
    )
    @pytest.mark.parametrize("price", [None, 0])
    def test_a_priced_event_without_a_price_is_refused(self, pricing, price) -> None:
        event = _publishable(pricing, price)

        with pytest.raises(ValueError, match="demande un prix"):
            event.publish()

        assert event.status == PublicationStatus.DRAFT, "un refus ne publie rien"

    def test_a_negative_price_is_refused(self) -> None:
        event = _publishable(EventPricing.PAID, -100)

        with pytest.raises(ValueError, match="demande un prix"):
            event.publish()

    def test_a_positive_price_publishes(self) -> None:
        event = _publishable(EventPricing.PAID, 4500)

        event.publish()

        assert event.status == PublicationStatus.PUBLIC
        assert event.price == 4500


class TestTheResidualPriceIsCleared:
    """PRX-03 — repasser le tarif à « gratuit » après avoir saisi un
    montant ne doit pas laisser le montant derrière."""

    def test_publishing_a_free_event_wipes_its_price(self) -> None:
        event = _publishable(EventPricing.FREE_FOR_ALL, 4500)

        event.publish()

        assert event.price is None

    def test_and_a_free_event_without_a_price_stays_fine(self) -> None:
        event = _publishable(EventPricing.FREE_FOR_ALL)

        event.publish()

        assert event.price is None


class TestAnUnknownPricingFails:
    """Trois branches explicites, pas de fourre-tout.

    Un `pricing` inattendu — `None` sur un objet jamais enregistré, une
    valeur ajoutée à l'énumération sans passer par ici — tombait dans la
    branche « gratuit pour les journalistes » et annonçait un tarif faux
    plutôt que d'échouer.
    """

    def test_none_raises_instead_of_lying(self) -> None:
        with pytest.raises(ValueError, match="inconnue"):
            price_label(_Event(None, 4500), OTHER)

    def test_and_so_does_a_stray_value(self) -> None:
        with pytest.raises(ValueError, match="inconnue"):
            price_label(_Event("half_price", 4500), JOURNALIST)


class TestADraftWithoutItsPriceYet:
    """`_settle_price` ne s'exécute qu'à la publication : un brouillon
    payant sans prix se rend donc, et affiche un tiret plutôt que de
    planter. C'est le bon comportement pour un aperçu de saisie."""

    def test_a_missing_price_shows_a_dash(self) -> None:
        assert price_label(_Event(EventPricing.PAID), OTHER) == "—"

    def test_and_reads_oddly_but_harmlessly_for_journalists_pricing(self) -> None:
        label = price_label(_Event(EventPricing.FREE_FOR_JOURNALISTS), OTHER)

        assert label == "— — gratuit pour les journalistes"
