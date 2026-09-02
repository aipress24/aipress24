# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from arrow import now
from loguru import logger
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.lib.geoloc import parse_pays_zip_ville
from app.models.lifecycle import PublicationStatus
from app.modules.events.change_detection import describe_state, has_changed, snapshot
from app.modules.events.models import EventPost
from app.modules.events.notifications import notify_event_changed
from app.modules.wip.models.eventroom import Event
from app.signals import (
    event_published,
    event_unpublished,
    event_updated,
)


@event_published.connect
def on_publish_event(event: Event) -> None:
    logger.debug("Received 'Event published': {}", event.title)
    post = get_post(event)
    if not post:
        post = EventPost()
        post.eventroom_id = event.id
        post.created_at = event.created_at
        post.published_at = now(LOCAL_TZ)

    post.status = PublicationStatus.PUBLIC

    update_post(post, event)

    db.session.add(post)
    db.session.flush()


@event_unpublished.connect
def on_unpublish_event(event: Event) -> None:
    logger.debug("Event unpublished: {}", event.title)
    post = get_post(event)
    if not post:
        return
    post.status = PublicationStatus.DRAFT

    db.session.add(post)
    db.session.flush()


@event_updated.connect
def on_update_event(event: Event) -> None:
    logger.debug("Received 'Event updated': {}", event.title)
    post = get_post(event)
    if not post:
        # Article not published yet, nothing to do
        return

    logger.debug("Updating post: {}", post)

    # NOT-11 — le miroir porte encore l'ancien état tant que
    # `update_post` ne l'a pas écrasé : la photographier avant et après
    # suffit, sans rien savoir du modèle de saisie.
    # (`modified_at` est déjà horodaté par `lifecycle_before_update` ;
    # l'ancienne ligne `post.last_updated_at = ...` écrivait un
    # attribut qui n'est pas une colonne d'`EventPost`.)
    before = snapshot(post)
    update_post(post, event)
    after = snapshot(post)

    db.session.add(post)
    db.session.flush()

    if has_changed(before, after):
        notify_event_changed(post, describe_state(before, after))


def event_type_to_category(event_type: str) -> str:
    first_part = event_type.split("/", maxsplit=1)[0]
    return first_part.strip().replace(" ", "_").lower()


def update_post(
    post: EventPost,
    info: Event,
) -> None:
    post.title = info.title
    post.summary = info.chapo
    post.content = info.contenu
    post.owner_id = info.owner_id
    # Bugs #0135/#0138: propagate publisher_id so the client/agency BW
    # `WHERE EventPost.publisher_id == org.id` query finds the event.
    # The same propagation is done for articles (wire/receivers.py).
    post.publisher_id = info.publisher_id

    # Schedule
    post.start_datetime = info.start_time  # type: ignore[assignment]
    post.end_datetime = info.end_time  # type: ignore[assignment]

    # Location
    post.address = info.address
    post.pays_zip_ville = info.pays_zip_ville
    post.pays_zip_ville_detail = info.pays_zip_ville_detail
    # Découpée ici, et ici seulement : c'est le seul endroit où la
    # localisation entre dans le miroir public.
    localisation = parse_pays_zip_ville(info.pays_zip_ville_detail)
    post.code_postal = localisation.code_postal
    post.departement = localisation.departement
    post.ville = localisation.ville

    post.genre = info.event_type
    post.sector = info.sector
    post.section = info.section
    post.topic = info.topic
    post.audience = list(info.audience or [])
    # Décision `M1` — ces deux axes ne servent qu'au miroir public :
    # c'est lui que la barre de filtres interroge.
    post.competences = list(info.competences or [])
    post.fonctions = list(info.fonctions or [])
    post.category = event_type_to_category(info.event_type)

    # Mode de participation. `access_details` est recopié parce que le
    # rappel de la veille en a besoin (NOT-13) ; c'est le seul endroit
    # où un accrédité le voit.
    post.mode = info.mode
    post.platform = info.platform
    post.access_details = info.access_details

    # Tarif. Recopié tel quel, centimes compris : la conversion en
    # euros appartient à l'affichage, pas au stockage.
    post.pricing = info.pricing
    post.price = info.price
    post.currency = info.currency

    # Organisateur (ORG-01). Recopié même quand il est vide : c'est le
    # cas ordinaire, et la cascade ORG-03 retombe alors sur l'éditeur.
    post.organiser_id = info.organiser_id
    post.organiser_name = info.organiser_name

    # Annulation (ANN-04) : le miroir barre l'annonce, il lui faut donc
    # la date et le motif. Aucun des deux n'est surveillé par NOT-11 —
    # une annulation n'est pas un changement d'horaire, elle a sa
    # propre notification (NOT-05), émise par la route qui l'a décidée.
    post.cancelled_at = info.cancelled_at
    post.cancellation_reason = info.cancellation_reason

    post.url = info.url
    post.language = info.language


def get_post(info: Event) -> EventPost | None:
    stmt = select(EventPost).where(EventPost.eventroom_id == info.id)
    result = db.session.execute(stmt)
    post = result.scalar_one_or_none()
    return post
