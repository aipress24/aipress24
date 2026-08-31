# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Notifications d'accréditation — `NOT-01` à `NOT-05`.

Rien n'est construit ici : `NotificationService` alimente déjà la
cloche, `EmailTemplate` sait envoyer. Ce module câble les transitions
d'accréditation sur ces deux canaux, et tient les messages au même
endroit — un texte de notification se relit mieux à côté de ses
voisins qu'au milieu d'une requête SQL.

Le canal est choisi par notification, pas par confort : la cloche
suffit à ce qui se consulte, l'email s'ajoute à ce dont dépend un
déplacement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from svcs.flask import container

from app.constants import LOCAL_TZ
from app.logging import report_failure
from app.models.lifecycle import PublicationStatus
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.events.models import EventPost


def notify_request_received(event: EventPost, requester: User) -> None:
    """NOT-01 — une demande arrive (RG-03).

    Vers l'organisateur : sans elle, rien ne lui signale qu'on attend
    une décision de sa part.
    """
    _post(
        event.owner,
        f"{requester.full_name} demande une accréditation à votre "
        f"événement « {event.title} ».",
        _event_url(event),
    )


def notify_accepted(event: EventPost, member: User) -> None:
    """NOT-02 — accréditation accordée (RG-06, RG-13).

    Cloche **et** email : c'est l'information qui décide d'un
    déplacement, elle ne peut pas dépendre d'un retour sur le site.
    """
    when = event.start_datetime.format("DD/MM/YYYY") if event.start_datetime else ""
    _post(
        member,
        f"Vous êtes accrédité.e à l'événement « {event.title} »"
        + (f" du {when}." if when else "."),
        _event_url(event),
    )
    _mail_accepted(event, member, when)


def notify_rejected(event: EventPost, member: User) -> None:
    """NOT-03 — demande refusée, ou accréditation retirée (RG-07, RG-09).

    Cloche seulement : un refus n'a pas à forcer un email.
    """
    _post(
        member,
        f"Votre demande d'accréditation à l'événement « {event.title} » "
        f"n'a pas été retenue.",
        _event_url(event),
    )


def notify_withdrawn(event: EventPost, member: User) -> None:
    """NOT-04 — le membre se retire (RG-08).

    Vers l'organisateur : une désinscription libère une place.
    """
    _post(
        event.owner,
        f"{member.full_name} s'est désinscrit.e de votre événement « {event.title} ».",
        _event_url(event),
    )


def _post(receiver: User | None, message: str, url: str) -> None:
    """Poser une notification, sans faire échouer la transition.

    Une cloche qui n'arrive pas est un incident ; une décision
    d'accréditation perdue parce que la cloche a échoué en serait un
    plus grave. L'échec est remonté, pas avalé.
    """
    if receiver is None:
        return
    try:
        container.get(NotificationService).post(receiver, message, url=url)
    except Exception as exc:
        report_failure(f"events: notification failed for user {receiver.id}", exc)


def _event_url(event: EventPost) -> str:
    from app.flask.routing import url_for

    return url_for("events.event", id=event.id)


def _mail_accepted(event: EventPost, member: User, when: str) -> None:
    from app.services.emails import AccreditationAcceptedMail

    organiser = event.owner
    try:
        AccreditationAcceptedMail(
            sender="contact@aipress24.com",
            recipient=member.email or "",
            sender_mail=(organiser.email if organiser else "")
            or "contact@aipress24.com",
            recipient_full_name=member.full_name,
            event_title=event.title,
            event_date=when,
            event_url=_event_url(event),
        ).send()
    except Exception as exc:
        report_failure(f"events: accreditation email failed (event {event.id})", exc)


def notify_event_changed(event: EventPost, changes: list[str]) -> None:
    """NOT-08 — l'événement a changé de date, de lieu ou d'adresse.

    Vers tous les accrédités, et vers eux seuls : une demande en cours
    n'est pas une place réservée.

    Posté en **groupé** : plusieurs modifications dans la fenêtre n'en
    produiront qu'une, portant l'état final (NOT-12). Le regroupement
    appartient au service de notifications ; ici on se contente de
    poster sous une clé stable.
    """
    from app.modules.events.services import get_participants

    if event.status != PublicationStatus.PUBLIC:
        return

    detail = " ".join(changes)
    message = f"L'événement « {event.title} » a été modifié. {detail}"
    url = _event_url(event)
    when = (
        event.start_datetime.to(LOCAL_TZ).format("DD/MM/YYYY")
        if event.start_datetime
        else ""
    )

    service = container.get(NotificationService)
    for member in get_participants(event):
        try:
            service.post_grouped(
                member,
                f"event-changed:{event.id}",
                message,
                url,
                mail_template="EventChangedMail",
                mail_kwargs={
                    "sender": "contact@aipress24.com",
                    "recipient": member.email or "",
                    "sender_mail": "contact@aipress24.com",
                    "recipient_full_name": member.full_name,
                    "event_title": event.title,
                    "event_date": when,
                    "changes": detail,
                    "event_url": url,
                },
            )
        except Exception as exc:
            report_failure(
                f"events: change notification failed (event {event.id})", exc
            )
