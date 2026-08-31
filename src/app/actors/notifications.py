# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tâche périodique de livraison des notifications groupées."""

from __future__ import annotations

from loguru import logger

from app.dramatiq.scheduler import crontab
from app.flask.extensions import db
from app.services.notifications import claim_due_notifications, send_claimed_mails


@crontab("*/2 * * * *")
def deliver_grouped_notifications() -> None:
    """Drainer la file d'attente toutes les deux minutes.

    La dueness ne s'évalue qu'au déclenchement, donc le pas s'ajoute à
    la fenêtre : à dix minutes, une notification ancrée à *t* partait
    entre *t*+30 et *t*+40, et une modification arrivant dans cette
    traîne fusionnait dans une ligne que la règle dit déjà livrée. À
    deux minutes, l'écart tombe sous le seuil de perception et les deux
    cas que NOT-12 nomme — cinq minutes, quarante-cinq minutes —
    tombent juste quelle que soit la phase.

    Le tour ne fait rien quand la file est vide : une requête indexée
    sur `first_seen_at`.
    """
    # Valider **avant** d'envoyer : un envoi est irréversible, et il ne
    # doit jamais précéder l'écriture qui dit qu'il a eu lieu. Sinon un
    # tour interrompu renvoie tout ce qu'il avait déjà expédié.
    mails = claim_due_notifications(db.session)
    db.session.commit()
    if mails:
        send_claimed_mails(mails)
        logger.info(f"cron: delivered {len(mails)} grouped notification(s)")


@crontab("2 * * * *")
def send_event_reminders() -> None:
    """Rappeler la veille les événements du lendemain.

    Toutes les heures, et non une fois par jour à 09:00 : c'est le
    registre d'envoi qui garantit l'unicité, pas la rareté du
    déclenchement. Un tour manqué se rattrape ainsi au suivant, alors
    qu'un crontab quotidien perdrait la journée.

    À la minute 2, pour ne pas se disputer l'heure juste avec la
    réputation.
    """
    from app.modules.events.reminders import (
        claim_due_reminders,
        send_claimed_reminders,
    )

    # Même ordre qu'au drainage : réserver, valider, puis envoyer.
    mails = claim_due_reminders(db.session)
    db.session.commit()
    if mails:
        send_claimed_reminders(mails)
        logger.info(f"cron: sent {len(mails)} event reminder(s)")
