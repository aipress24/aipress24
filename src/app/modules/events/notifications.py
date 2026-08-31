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

from enum import StrEnum
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
    """L'adresse publique de l'événement, absolue quand c'est possible.

    Un lien relatif est parfaitement lisible dans la cloche, et
    parfaitement mort dans un client mail — or le même helper alimente
    les deux. `_external=True` échoue si `SERVER_NAME` n'est pas
    configuré : on retombe alors sur le chemin, qui reste juste pour la
    cloche.
    """
    from app.flask.routing import url_for

    try:
        return url_for("events.event", id=event.id, _external=True)
    except Exception:
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


def notify_event_changed(event: EventPost, details: list[str]) -> None:
    """NOT-08 — l'événement a changé de date, de lieu ou d'adresse.

    Vers tous les accrédités, et vers eux seuls : une demande en cours
    n'est pas une place réservée.

    Posté en **groupé** : plusieurs modifications dans la fenêtre n'en
    produiront qu'une, portant l'état final (NOT-12). Le regroupement
    appartient au service de notifications ; ici on se contente de
    poster sous une clé stable.

    Le message décrit l'**état courant** et non ce qui a bougé. Un
    delta ne survit pas à la fusion : le message qui remplace emporte
    celui qu'il remplace, et un membre prévenu d'un changement
    d'adresse ne saurait jamais que la date avait bougé aussi. C'est un
    écart assumé au libellé de la spécification, qui donne « la date
    passe du 12 au 19 mars » en exemple — plus agréable à lire, et
    incompatible avec le regroupement qu'elle demande par ailleurs.
    """
    from app.modules.events.services import get_participants

    if event.status != PublicationStatus.PUBLIC:
        return
    if event.cancelled_at is not None:
        # Un événement annulé reste `PUBLIC` (ANN-03) : sans cette
        # garde, corriger l'adresse d'un événement qu'on vient
        # d'annuler enverrait « l'événement a été modifié » à des gens
        # qui savent déjà qu'il n'aura pas lieu.
        return

    detail = " ".join(details)
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


class EventStatusChange(StrEnum):
    """Les trois déclencheurs de NOT-05 (§9.2).

    Annulation, rétablissement et dépublication disent la même chose à
    la même personne — « l'événement auquel vous êtes accrédité n'aura
    pas lieu comme annoncé » — et n'appellent qu'un gabarit, dont le
    corps varie.
    """

    CANCELLED = "cancelled"
    RESTORED = "restored"
    UNPUBLISHED = "unpublished"


#: Texte de cloche et objet d'email, par déclencheur. Le **corps** de
#: l'email vit dans son gabarit (NOT-18) ; la cloche n'en a pas, et
#: c'est le seul texte que ce module compose.
_STATUS_CHANGE_TEXT: dict[EventStatusChange, tuple[str, str]] = {
    EventStatusChange.CANCELLED: (
        "L'événement « {title} »{when} a été annulé par son organisateur.",
        "[Aipress24] Un événement de votre agenda est annulé",
    ),
    EventStatusChange.RESTORED: (
        (
            "L'événement « {title} »{when} est finalement maintenu : "
            "son organisateur a levé l'annulation."
        ),
        "[Aipress24] Un événement de votre agenda est rétabli",
    ),
    EventStatusChange.UNPUBLISHED: (
        (
            "L'annonce de l'événement « {title} »{when} a été retirée "
            "par son organisateur."
        ),
        "[Aipress24] Une annonce de votre agenda a été retirée",
    ),
}


def notify_status_change(event: EventPost, change: EventStatusChange) -> int:
    """NOT-05 — l'événement n'aura pas lieu comme annoncé (RG-12).

    Vers tous les accrédités, et vers eux seuls : une demande en cours
    n'est pas une place réservée. Cloche **et** email, quelles que
    soient les préférences (NOT-17) — c'est une information dont dépend
    un déplacement.

    **Aucune garde sur le statut**, contrairement à NOT-08 : la
    dépublication fait passer le miroir en `DRAFT` avant l'envoi, et
    une garde « seulement si PUBLIC » avalerait silencieusement toutes
    les notifications de ce déclencheur-là.

    Pas de regroupement non plus. Il est destructif — le message qui
    remplace emporte celui qu'il remplace — et une annulation suivie
    d'un rétablissement dans la fenêtre ne livrerait que le second : le
    membre n'apprendrait jamais que son événement avait été annulé,
    quand ANN-07 dit précisément qu'une annulation annoncée est un fait
    public qu'on n'efface pas.

    Renvoie le nombre de membres prévenus. **À appeler après le
    `commit`** qui enregistre le changement : un email est irréversible
    et ne doit jamais précéder l'écriture qui le justifie.
    """
    from app.modules.events.services import get_participants

    bell_text, subject = _STATUS_CHANGE_TEXT[change]
    when = (
        event.start_datetime.to(LOCAL_TZ).format("DD/MM/YYYY")
        if event.start_datetime
        else ""
    )
    message = bell_text.format(title=event.title, when=f" du {when}" if when else "")
    url = _event_url(event)

    members = get_participants(event)
    for member in members:
        _post(member, message, url)
        _mail_status_change(event, member, change, subject, when)
    return len(members)


def _mail_status_change(
    event: EventPost,
    member: User,
    change: EventStatusChange,
    subject: str,
    when: str,
) -> None:
    from app.services.emails import EventCancelledMail

    try:
        EventCancelledMail(
            sender="contact@aipress24.com",
            recipient=member.email or "",
            sender_mail="contact@aipress24.com",
            subject=subject,
            recipient_full_name=member.full_name,
            event_title=event.title,
            event_date=when,
            change=str(change.value),
            reason=event.cancellation_reason or "",
            event_url=_event_url(event),
        ).send()
    except Exception as exc:
        report_failure(f"events: NOT-05 mail failed (event {event.id})", exc)


def notify_submitted_for_review(event, reviewers) -> int:
    """NOT-06 — un événement attend une relecture (REL-07).

    Vers les rôles habilités de l'organisation éditrice. Cloche
    seulement : la relecture est un travail d'atelier, pas une
    information dont dépend un déplacement.

    `event` est l'événement de **saisie** et non le miroir public : à ce
    stade il n'y en a pas, l'événement n'a jamais été publié. D'où
    l'adresse vers l'atelier plutôt que vers la page publique, et la
    liste de destinataires passée par l'appelant, qui seul sait
    interroger le Business Wall.

    Renvoie le nombre de relecteurs prévenus.
    """
    from app.flask.routing import url_for

    url = url_for("EventsWipView:get", id=event.id)
    author = event.owner
    message = (
        f"{author.full_name if author else 'Un membre'} soumet l'événement "
        f"« {event.title} » à votre relecture."
    )
    for reviewer in reviewers:
        _post(reviewer, message, url)
    return len(reviewers)


def notify_sent_back(event, comment: str) -> None:
    """NOT-07 — l'événement revient à son auteur, avec le motif (REL-07).

    Le motif est le contenu utile du message : sans lui, l'auteur sait
    que son événement est revenu mais pas ce qu'il doit corriger. Il
    n'est conservé nulle part ailleurs — la spécification ne le demande
    pas, et un renvoi est un échange, pas un état.
    """
    from app.flask.routing import url_for

    _post(
        event.owner,
        f"Votre événement « {event.title} » vous est renvoyé pour "
        f"correction : {comment.strip()}",
        url_for("EventsWipView:edit", id=event.id),
    )
