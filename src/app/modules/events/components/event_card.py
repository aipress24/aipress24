# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from arrow import Arrow
from attr import define
from flask import g

from app.flask.lib.pywire import Component, component
from app.flask.lib.view_model import ViewModel
from app.lib.utils import split_taxonomy_value
from app.modules.bw.bw_activation.user_utils import get_organisation_logo_url
from app.modules.events.components.opening_hours import opening_hours
from app.modules.events.models import EventPost
from app.modules.events.pricing import price_label

DEFAULT_LOGO_URL = "/static/img/transparent-square.png"


@define
class EventCardVM(ViewModel):
    """View model for event card component."""

    def extra_attrs(self) -> dict:
        event = cast("EventPost", self._model)

        # Compute opening hours only if both dates are set
        if event.start_datetime and event.end_datetime:
            start = cast(Arrow, event.start_datetime)
            end = cast(Arrow, event.end_datetime)
            opening = opening_hours(start, end)
        else:
            opening = ""

        return {
            "author": event.owner,
            "organisation_image_url": self._get_organisation_logo_url(),
            # `genre` is written "FAMILY / Detail"; the card shows the
            # family, with the taxonomy's own case — `category`
            # lower-cases it for filtering and cannot serve as a label.
            "genre_family": split_taxonomy_value(event.genre)[0] or event.category,
            "opening": opening,
            "likes": event.like_count,
            "replies": event.comment_count,
            "views": event.view_count,
            # §7.2 — la pastille « Accrédité.e ». Renseignée par la vue
            # liste, qui charge toutes les accréditations de la page en
            # une requête ; **fausse partout ailleurs**, par le défaut
            # déclaré sur le modèle.
            #
            # C'est cette clé qu'il faut poser ici, et non se reposer
            # sur `EventListVM` : la carte est rendue à deux
            # profondeurs d'enveloppe —
            # `EventCardVM(EventListVM(EventPost))` sur la liste, et
            # `EventCardVM(EventPost)` sur le Business Wall d'une
            # organisation, qui passe la ligne brute. Sur le second
            # chemin la clé n'existait pas, et comme les gabarits sont
            # rendus en `StrictUndefined`, la rubrique Événements du
            # Business Wall **plantait** depuis le lot L2.
            "is_accredited": event.is_accredited,
            # PRX-04 — le tarif dépend du lecteur. Posé ici pour la
            # même raison que la pastille ci-dessus : c'est le seul
            # view model qui enveloppe sur les deux chemins de rendu.
            "price_label": price_label(event, getattr(g, "user", None)),
        }

    def _get_organisation_logo_url(self) -> str:
        """Get the organisation logo URL from the event owner."""

        event = cast("EventPost", self._model)
        owner = event.owner
        if owner and owner.organisation:
            return get_organisation_logo_url(owner.organisation)
        return DEFAULT_LOGO_URL


@component
@define
class EventCard(Component):
    event: EventPost
    # Accepted for parity with `PostCard`: the org / member tab
    # includes call every card the same way —
    # `component("…-card", obj, class_="bg-gray-100")`. Without this
    # field the events tab 500s with « unexpected keyword argument
    # 'class_' » (prod fe36ebd9). Kept optional so the bare
    # positional call still works.
    class_: str = ""

    def __attrs_post_init__(self) -> None:
        # Wrap event in ViewModel for clean computed property access
        self.event = EventCardVM(self.event)
