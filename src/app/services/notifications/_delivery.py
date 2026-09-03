# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Livraison des notifications groupées.

Draine la file alimentée par `NotificationService.post_grouped` : une
notification dont la fenêtre est écoulée devient une cloche, et un
email si l'appelant en a décrit un.

**L'envoi ne précède jamais l'écriture qui dit qu'il a eu lieu.** D'où
le découpage en deux temps : le service s'approprie les lignes et pose
les cloches, l'appelant valide, puis envoie. Tant que la validation
venait après l'envoi, un tour interrompu annulait les réservations en
laissant les mails partis — et le tour suivant les renvoyait tous, ce
que Dramatiq répète jusqu'à vingt fois.

Le service ne valide pas lui-même : les frontières de transaction
appartiennent à qui orchestre, pas à qui écrit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow

from app.logging import report_failure

from ._models import Notification, PendingNotification

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

WINDOW_MINUTES = 30


def claim_due_notifications(
    session: Session,
    now: arrow.Arrow | None = None,
    *,
    window_minutes: int = WINDOW_MINUTES,
    limit: int = 200,
) -> list[dict]:
    """S'approprier les notifications dues et poser leurs cloches.

    Renvoie les descriptions d'email à envoyer **après validation**.
    `now` est un paramètre et non une lecture d'horloge : c'est la
    seule façon de tester une fenêtre dans un dépôt qui ne sait pas
    geler le temps.

    `limit` borne un rattrapage après une panne du planificateur : un
    drainage qui ne finit pas est pire qu'un drainage partiel, et le
    tour suivant reprend la suite.
    """
    now = now or arrow.utcnow()
    cutoff = now.shift(minutes=-window_minutes)

    due = (
        session.query(PendingNotification)
        .filter(PendingNotification.first_seen_at <= cutoff)
        .order_by(PendingNotification.first_seen_at)
        .limit(limit)
        .all()
    )

    mails = []
    for pending in due:
        payload = _payload(pending)
        if not _claim(session, pending):
            # Un autre drainage l'a prise. Deux tours peuvent se
            # chevaucher : le planificateur enfile sans savoir si le
            # précédent a fini.
            continue
        session.add(
            Notification(
                receiver_id=payload["receiver_id"],
                message=payload["message"],
                url=payload["url"],
            )
        )
        if payload["mail_template"]:
            mails.append(payload)

    return mails


def send_claimed_mails(mails: list[dict]) -> int:
    """Envoyer les emails d'un lot déjà validé. Renvoie le nombre parti.

    À n'appeler qu'après le `commit` : c'est ce qui rend la perte
    possible mais le doublon impossible. Pour un changement de date
    annoncé à tous les accrédités, l'inondation est le pire des deux.
    """
    sent = 0
    for payload in mails:
        if _send_mail(payload):
            sent += 1
    return sent


def _payload(pending: PendingNotification) -> dict:
    """Détacher ce dont l'envoi a besoin avant de supprimer la ligne."""
    return {
        "receiver_id": pending.receiver_id,
        "message": pending.message,
        "url": pending.url,
        "mail_template": pending.mail_template,
        "mail_kwargs": dict(pending.mail_kwargs or {}),
    }


def _claim(session: Session, pending: PendingNotification) -> bool:
    """S'approprier une ligne, ou constater qu'un autre l'a prise.

    Le retrait fait office de verrou : `rowcount` dit qui a gagné.
    """
    count = (
        session.query(PendingNotification)
        .filter(PendingNotification.id == pending.id)
        .delete(synchronize_session=False)
    )
    return bool(count)


def _send_mail(payload: dict) -> bool:
    """Construire et envoyer l'email décrit par l'appelant.

    L'échec est remonté, pas propagé : la cloche est déjà posée et
    validée, et perdre le reste du lot parce que SMTP a hoqueté serait
    pire.

    Un nom de gabarit inconnu est en revanche une **erreur de
    programmation** — un renommage de classe non répercuté aux lignes
    en attente — et non un aléa d'exploitation. Il est signalé comme
    tel, pour ne pas se perdre parmi les hoquets SMTP.
    """
    name = payload["mail_template"]
    from app.services import emails

    mailer = getattr(emails, name, None)
    if mailer is None:
        report_failure(
            f"notifications: no mailer named {name!r} — a rename was not "
            "propagated to the queued rows",
            LookupError(name),
        )
        return False

    # No `except`: `EmailTemplate.send()` already catches `SMTPException`
    # and returns a bool, so anything raised here is a programming error
    # — wrong kwargs, missing template — and must surface.
    return mailer(**payload["mail_kwargs"]).send()
