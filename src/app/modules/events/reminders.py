# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Rappel de la veille — `NOT-09`, `NOT-13`, `NOT-14`.

Un membre accrédité est prévenu la veille de l'événement. Le rappel ne
passe pas par la livraison groupée : il n'est pas répété, et le
différer de trente minutes contredirait l'heure qu'on lui fixe.
"""

from __future__ import annotations

import arrow
import sqlalchemy as sa

from app.constants import LOCAL_TZ
from app.logging import report_failure
from app.models.lifecycle import PublicationStatus
from app.services.notifications import Notification

from .models import (
    Accreditation,
    AccreditationStatus,
    EventPost,
    NotificationKind,
    NotificationSent,
)

#: Heure parisienne à partir de laquelle le rappel de la veille est dû.
REMINDER_HOUR = 9


def reminder_date(now: arrow.Arrow):
    """La date d'événement dont le rappel est dû à cet instant.

    `None` avant l'heure. Le seuil se lit **au plus tôt** et non
    **exactement** : une tâche horaire qui n'agit qu'à l'heure juste
    perd une journée entière de rappels dès qu'un tour est manqué,
    alors qu'avec « au plus tôt » le tour suivant rattrape et que le
    registre rend les autres inertes.

    L'heure est lue à Paris parce que le planificateur ne l'est pas :
    `BlockingScheduler()` est construit sans `timezone=`, donc un
    crontab « 0 9 * * * » déclencherait à 11:00 à Paris sur un serveur
    en UTC.
    """
    local = now.to(LOCAL_TZ)
    if local.hour < REMINDER_HOUR:
        return None
    return local.shift(days=1).date()


#: Plafond d'un tour. Un rattrapage qui ne finit pas est pire qu'un
#: rattrapage partiel : Dramatiq coupe l'acteur à dix minutes et le
#: rejoue, et le tour suivant reprend la suite de toute façon.
BATCH_LIMIT = 200


def claim_due_reminders(
    session, now: arrow.Arrow | None = None, *, limit: int = BATCH_LIMIT
) -> list[dict]:
    """S'approprier les rappels dus et poser leurs cloches.

    Renvoie les descriptions d'email à envoyer **après validation** :
    un envoi est irréversible et ne doit jamais précéder l'écriture qui
    dit qu'il a eu lieu. Le service ne valide pas lui-même — les
    frontières de transaction appartiennent à qui orchestre.

    `now` est un paramètre et non une lecture d'horloge : c'est la
    seule façon de tester une règle horaire dans un dépôt qui ne sait
    pas geler le temps.
    """
    now = now or arrow.utcnow()
    target = reminder_date(now)
    if target is None:
        return []

    day_start = arrow.get(target, tzinfo=LOCAL_TZ)
    stmt = (
        sa.select(EventPost)
        .where(EventPost.status == PublicationStatus.PUBLIC)
        .where(EventPost.start_datetime >= day_start)
        .where(EventPost.start_datetime < day_start.shift(days=1))
        # NOT-15 — un événement annulé reste `PUBLIC` (ANN-03) : sans
        # cette clause, ses accrédités recevraient « a lieu demain » le
        # lendemain de l'annonce de l'annulation.
        .where(EventPost.cancelled_at.is_(None))
    )

    # Matérialisé : la réservation ouvre une sous-transaction, ce qui
    # ne se fait pas au milieu d'un curseur encore ouvert.
    mails: list[dict] = []
    for event in session.scalars(stmt).all():
        if len(mails) >= limit:
            break
        _remind_one(session, event, target, mails, limit)
    return mails


def _remind_one(
    session, event: EventPost, target, mails: list[dict], limit: int
) -> None:
    key = target.isoformat()
    members = session.scalars(
        sa.select(Accreditation).where(
            Accreditation.event_id == event.id,
            Accreditation.status == AccreditationStatus.ACCEPTED,
        )
    ).all()

    for accreditation in members:
        if len(mails) >= limit:
            return
        if not _claim(session, event.id, accreditation.user_id, key):
            continue
        mails.append(_bell_and_payload(session, event, accreditation.user))


def _claim(session, event_id: int, user_id: int, key: str) -> bool:
    """Réserver l'envoi, ou constater qu'il a déjà eu lieu.

    Deux protections, de portées différentes :

    - la **lecture** couvre le rejeu, qui est ce que NOT-14 nomme : la
      tâche est horaire, tous les tours qui suivent le premier passent
      ici et repartent ;
    - la **contrainte d'unicité** couvre la simultanéité vraie, bien
      plus rare — deux tours qui se chevauchent. Elle empêche le
      doublon d'être *enregistré* ; le perdant échoue à valider sa
      transaction et son tour est perdu, ce qui est le bon sens de la
      perte pour un rappel dont le suivant rattrapera.

    Pas de sous-transaction ici : la fixture de test pose son propre
    savepoint et le relance à chaque fin de transaction, ce qui rend
    `begin_nested` inutilisable sous pytest — et un mécanisme
    d'unicité qu'on ne peut pas tester ne protège rien.
    """
    already = session.scalar(
        sa.select(NotificationSent.id).where(
            NotificationSent.event_id == event_id,
            NotificationSent.user_id == user_id,
            NotificationSent.kind == NotificationKind.REMINDER,
            NotificationSent.dedup_key == key,
        )
    )
    if already is not None:
        return False

    session.add(
        NotificationSent(
            event_id=event_id,
            user_id=user_id,
            kind=NotificationKind.REMINDER,
            dedup_key=key,
        )
    )
    session.flush()
    return True


def _bell_and_payload(session, event: EventPost, member) -> dict:
    """Poser la cloche, et décrire l'email à envoyer après validation.

    Aucune exception n'est attrapée ici. Une écriture qui échoue laisse
    la session inutilisable : continuer la boucle ferait échouer tout
    ce qui suit, en donnant l'illusion d'un incident isolé. Mieux vaut
    que le tour s'arrête et soit rejoué.
    """
    when = event.start_datetime.to(LOCAL_TZ).format("DD/MM/YYYY à HH:mm")
    url = _reminder_url(event)

    session.add(
        Notification(
            receiver_id=member.id,
            message=f"Rappel : l'événement « {event.title} » a lieu demain, {when}.",
            url=url,
        )
    )
    return {
        "sender": "contact@aipress24.com",
        "recipient": member.email or "",
        "sender_mail": "contact@aipress24.com",
        "recipient_full_name": member.full_name,
        "event_title": event.title,
        "event_date": when,
        "event_url": url,
        # NOT-13. Dans l'**email** et non dans la cloche : celle-ci est
        # stockée en clair dans une table de notifications rendue par
        # une liste générique, sans garde propre à l'événement.
        "access_details": event.access_details or "",
    }


def _reminder_url(event: EventPost) -> str:
    from .notifications import _event_url

    return _event_url(event)


def send_claimed_reminders(mails: list[dict]) -> int:
    """Envoyer les rappels d'un lot déjà validé.

    À n'appeler qu'après le `commit` : c'est ce qui rend la perte
    possible mais le doublon impossible.
    """
    from app.services.emails import EventReminderMail

    sent = 0
    for payload in mails:
        try:
            EventReminderMail(**payload).send()
            sent += 1
        except Exception as exc:
            report_failure(
                f"events: reminder mail failed for {payload['recipient']}", exc
            )
    return sent
