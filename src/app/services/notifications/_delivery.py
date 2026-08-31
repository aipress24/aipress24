# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Livraison des notifications groupées.

Draine la file d'attente alimentée par
`NotificationService.post_grouped` : une notification dont la fenêtre
est écoulée devient une cloche, et un email si l'appelant en a décrit
un.

La fenêtre est **fixe**, ancrée sur `first_seen_at`. Une session
d'édition continue ne repousse donc pas la livraison indéfiniment, et
deux modifications espacées de plus d'une fenêtre produisent bien deux
notifications — les deux cas que la règle NOT-12 nomme.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow

from app.logging import report_failure

from ._models import Notification, PendingNotification

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

WINDOW_MINUTES = 30


def deliver_due_notifications(
    session: Session,
    now: arrow.Arrow | None = None,
    *,
    window_minutes: int = WINDOW_MINUTES,
    limit: int = 200,
) -> int:
    """Livrer les notifications dont la fenêtre est écoulée.

    Renvoie le nombre livré. `now` est un paramètre et non une lecture
    d'horloge : c'est la seule façon de tester une fenêtre dans un
    dépôt qui ne sait pas geler le temps.

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

    delivered = 0
    for pending in due:
        if not _claim(session, pending):
            # Un autre drainage l'a prise. Deux tours peuvent se
            # chevaucher : le planificateur enfile sans savoir si le
            # précédent a fini.
            continue
        _deliver(session, pending)
        delivered += 1

    return delivered


def _claim(session: Session, pending: PendingNotification) -> bool:
    """S'approprier une ligne, ou constater qu'un autre l'a prise.

    Le retrait fait office de verrou : `rowcount` dit qui a gagné. On
    retire **avant** de livrer, donc un arrêt brutal entre les deux
    perd une notification plutôt que d'en dupliquer une — pour un
    changement de date annoncé à tous les accrédités, l'inondation est
    le pire des deux.
    """
    count = (
        session.query(PendingNotification)
        .filter(PendingNotification.id == pending.id)
        .delete(synchronize_session=False)
    )
    return bool(count)


def _deliver(session: Session, pending: PendingNotification) -> None:
    session.add(
        Notification(
            receiver_id=pending.receiver_id,
            message=pending.message,
            url=pending.url,
        )
    )
    if pending.mail_template:
        _send_mail(pending)


def _send_mail(pending: PendingNotification) -> None:
    """Construire et envoyer l'email décrit par l'appelant.

    L'échec est remonté, pas propagé : la cloche est déjà posée, et
    perdre la livraison entière parce que SMTP a hoqueté serait pire.
    """
    from app.services import emails

    try:
        mailer = getattr(emails, pending.mail_template)
        mailer(**pending.mail_kwargs).send()
    except Exception as exc:
        report_failure(
            f"notifications: grouped mail {pending.mail_template!r} failed", exc
        )
