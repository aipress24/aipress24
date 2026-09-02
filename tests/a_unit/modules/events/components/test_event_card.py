# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/components/event_card module.

Tests opening_hours formatting and EventCardVM view model.
"""

from __future__ import annotations

import arrow

from app.enums import EventPricing
from app.modules.events.components.event_card import (
    DEFAULT_LOGO_URL,
    EventCard,
    EventCardVM,
)
from app.modules.events.components.opening_hours import opening_hours


class TestOpeningHours:
    """Test suite for opening_hours function - tests the core date formatting logic."""

    def test_same_start_and_end(self):
        """Test opening hours when start and end times are the same."""
        start_time = arrow.get("2024-01-15 14:00:00").datetime
        result = opening_hours(start_time, start_time)
        assert result == "À 14:00 le 15 jan 2024"

    def test_different_start_and_end_same_day(self):
        """Test opening hours with different start and end times on same day."""
        start = arrow.get("2024-01-15 14:00:00").datetime
        end = arrow.get("2024-01-15 18:30:00").datetime
        result = opening_hours(start, end)
        assert result == "De 14:00 à 18:30 le 15 jan 2024"

    def test_morning_times(self):
        """Test opening hours with morning times."""
        start = arrow.get("2024-01-15 09:30:00").datetime
        end = arrow.get("2024-01-15 11:45:00").datetime
        result = opening_hours(start, end)
        assert result == "De 09:30 à 11:45 le 15 jan 2024"

    def test_midnight(self):
        """Test opening hours at midnight."""
        start = arrow.get("2024-01-15 00:00:00").datetime
        end = arrow.get("2024-01-15 23:59:00").datetime
        result = opening_hours(start, end)
        assert result == "De 00:00 à 23:59 le 15 jan 2024"

    def test_multi_day_event(self):
        """Test opening hours over multiple days."""
        start = arrow.get("2024-01-15 09:00:00").datetime
        end = arrow.get("2024-01-17 20:00:00").datetime
        result = opening_hours(start, end)
        assert result == "Du 15 jan 2024 à 09:00 au 17 jan 2024 à 20:00"


# Stub classes for testing EventCard/EventCardVM without database
class StubOrganisation:
    """Stub organisation for testing."""

    is_auto = True


class StubOwner:
    """Stub owner for events."""

    name = "Test Owner"
    organisation = None  # No org by default


class StubEvent:
    """Stub event for testing EventCard without database."""

    def __init__(
        self,
        start_datetime=None,
        end_datetime=None,
        owner=None,
        genre="Press / Conférence de presse",
        category="press",
        like_count=0,
        comment_count=0,
        view_count=0,
        pricing=EventPricing.FREE_FOR_ALL,
        price=None,
    ):
        # PRX-04 et §7.2 : le tarif et la pastille sont calculés par
        # `EventCardVM` pour tous les chemins de rendu, ils font donc
        # partie du contrat de la carte.
        self.is_accredited = False
        self.pricing = pricing
        self.price = price
        self.currency = "EUR"
        self.start_datetime = start_datetime or arrow.get("2024-01-15 10:00:00")
        self.end_datetime = end_datetime or arrow.get("2024-01-15 12:00:00")
        self.owner = owner or StubOwner()
        self.like_count = like_count
        self.comment_count = comment_count
        self.view_count = view_count
        self.title = "Test Event"
        self.summary = "Test Summary"
        # "FAMILY / Detail", and its normalised family: that is what
        # `event_receiver` writes, and what the card's chip uses.
        self.genre = genre
        self.category = category


class TestEventCardVM:
    """Test suite for EventCardVM view model."""

    def test_provides_author_from_owner(self):
        """Test that ViewModel exposes author from owner."""
        owner = StubOwner()
        event = StubEvent(owner=owner)

        vm = EventCardVM(event)

        assert vm.author == owner

    def test_provides_organisation_image_url_default(self):
        """Test that ViewModel provides default logo URL when no org."""
        event = StubEvent()

        vm = EventCardVM(event)

        assert vm.organisation_image_url == DEFAULT_LOGO_URL

    def test_provides_organisation_image_url_from_org(self):
        """Test that ViewModel gets logo URL from organisation."""
        owner = StubOwner()
        owner.organisation = StubOrganisation()
        event = StubEvent(owner=owner)

        vm = EventCardVM(event)

        assert vm.organisation_image_url == "/static/img/logo-page-non-officielle.png"

    def test_the_chip_shows_the_genre_family(self):
        """The family, with the taxonomy's own case.

        Replaces two `type_id`/`type_label` tests: they read a `Meta`
        that only the stub fabricated. `Event` had five subclasses
        carrying one; flattening them into a single `EventPost` took
        them away, and `get_meta_attr` has returned `""` in production
        ever since. The notion moved into the taxonomy.
        """
        vm = EventCardVM(StubEvent(genre="Business / Salon professionnel"))

        assert vm.genre_family == "Business"

    def test_without_a_genre_the_category_serves_as_label(self):
        """Legacy rows only have `category`, in lower case."""
        vm = EventCardVM(StubEvent(genre="", category="press"))

        assert vm.genre_family == "press"

    def test_provides_opening_hours(self):
        """Test that ViewModel exposes formatted opening hours."""
        event = StubEvent(
            start_datetime=arrow.get("2024-01-15 14:00:00"),
            end_datetime=arrow.get("2024-01-15 16:00:00"),
        )

        vm = EventCardVM(event)

        assert vm.opening == "De 14:00 à 16:00 le 15 jan 2024"

    def test_provides_engagement_counts(self):
        """Test that ViewModel exposes likes, replies, views."""
        event = StubEvent(like_count=10, comment_count=5, view_count=100)

        vm = EventCardVM(event)

        assert vm.likes == 10
        assert vm.replies == 5
        assert vm.views == 100

    def test_proxies_model_attributes(self):
        """Test that ViewModel proxies access to model attributes."""
        event = StubEvent()

        vm = EventCardVM(event)

        assert vm.title == "Test Event"
        assert vm.summary == "Test Summary"

    def test_with_neither_genre_nor_category_the_chip_disappears(self):
        """An empty family must not render an empty chip.

        This replaced a test of `get_meta_attr` defaults on an empty
        `Meta` — a shape production did not have. The question that
        actually arises is this one: `.chip` is an `inline-flex` with
        padding, so an empty value shows. The template renders the chip
        only when the value exists; it still has to be plainly empty.
        """
        vm = EventCardVM(StubEvent(genre="", category=""))

        assert vm.genre_family == ""


class TestEventCard:
    """Test suite for EventCard component."""

    def test_wraps_event_with_viewmodel(self):
        """Test that EventCard wraps event with EventCardVM."""
        event = StubEvent()

        card = EventCard(event=event)

        assert isinstance(card.event, EventCardVM)

    def test_wrapped_event_provides_computed_attrs(self):
        """Test that wrapped event provides computed attributes."""
        owner = StubOwner()
        event = StubEvent(owner=owner)

        card = EventCard(event=event)

        assert card.event.author == owner
        assert card.event.opening == "De 10:00 à 12:00 le 15 jan 2024"

    def test_accepts_class_kwarg(self):
        """Regression (prod fe36ebd9, 2026-05-14): the org events tab
        renders `component("event-card", event, class_="bg-gray-100")`
        — the same call shape the sibling tabs use for `post-card`
        (which accepts `class_`). EventCard must accept it too instead
        of raising `TypeError: __init__() got an unexpected keyword
        argument 'class_'` and 500-ing /swork/organisations/<id>."""
        event = StubEvent()

        card = EventCard(event=event, class_="bg-gray-100")

        assert card.class_ == "bg-gray-100"
        # The event is still wrapped — class_ doesn't break the VM.
        assert isinstance(card.event, EventCardVM)

    def test_class_kwarg_defaults_to_empty(self):
        """`class_` is optional — the bare positional call still works."""
        event = StubEvent()

        card = EventCard(event=event)

        assert card.class_ == ""


class TestDefaultLogoUrl:
    """Test suite for DEFAULT_LOGO_URL constant."""

    def test_default_logo_url_is_defined(self):
        """Test that DEFAULT_LOGO_URL constant is defined."""
        assert DEFAULT_LOGO_URL == "/static/img/transparent-square.png"


class TestTheCardSurvivesBothWrappingDepths:
    """La carte est rendue de deux façons, et l'une d'elles plantait.

    Sur `/events/`, la vue enveloppe chaque ligne dans un `EventListVM`
    avant de la donner à la carte : `EventCardVM(EventListVM(EventPost))`.
    Sur le Business Wall d'une organisation, `org--tab-events.html` passe
    la **ligne brute** : `EventCardVM(EventPost)`.

    Le lot L2 avait posé la pastille « Accrédité.e » sur une clé
    calculée par `EventListVM`, absente du second chemin. Les gabarits
    étant rendus en `StrictUndefined`, la rubrique Événements du
    Business Wall levait `UndefinedError` — un 500, pas une pastille
    manquante.
    """

    def test_the_key_exists_on_a_raw_model(self):
        """Le chemin du Business Wall."""
        event = StubEvent()

        assert EventCardVM(event)["is_accredited"] is False

    def test_and_carries_through_a_list_view_model(self):
        """Le chemin de la liste : la vue pose `_is_accredited` sur la
        ligne, et la carte doit le lire."""
        event = StubEvent()
        event.is_accredited = True

        assert EventCardVM(event)["is_accredited"] is True
